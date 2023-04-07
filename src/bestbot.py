import discord
from discord.ext import commands
import csv
import os
import datetime 
import pytz
import tabulate
import textwrap

# Important initialization stuff
# Apparently writing this OOP style is unreasonably difficult, alas
import DiscordIDs # not on Git, but useful for debugging

intents=discord.Intents.default()
intents.message_content = True
intents.members = True
client = commands.Bot(intents=intents,command_prefix='/')

# Global Variables (NEED TO BE SET MANUALLY)
TOKEN = DiscordIDs.BOT_TOKEN
DEBUG = True # May need to adjust the way this works

# ======================================
# ASYNCHRONOUS FUNCTIONS (commands, etc)
# ======================================

@client.event
async def on_ready():
    """Just does stuff when initially launched"""
    print("BEST BOT ONLINE PEW PEW")
    

async def scrape_messages(channel, save_to_file=False):
    """
    Scrape all messages and collects statistical data, if needed stores the 
    results in a local csv, including author, content and timestamp information
    
    Args:
        channel (obj): the channel to be scraped

    Returns:
        list: all message objects from the given channel
        dict: dict of dicts containing stats per member
            - member: the author
            - dict: stats
                - int: message count
                - delta: message difference
                - chars: character count
        dict: metadata for all messages from all users in the channel
            - int: message count
            - delta: message difference
            - chars: character count 
    """
    # Initialize
    print("Looking for messages...")
    channel = client.get_channel(channel.id)
    messages = []
    stats = {} # member : dict
    metadata = {"count": 0,
                "delta": 0,
                "chars": 0}

    # Turn it into a list (because too lazy to learn about async)
    # Also generate per-user stats
    async for message in channel.history(limit=None):
        messages.append(message)

        # Count total messages
        member = message.author
        if member not in stats:
            stats[member] = {"count": 0,
                             "delta": 0,
                             "chars": 0}
        stats[member]["count"] += 1
        stats[member]["chars"] += len(message.content)

        # Count new messages in past 30 days
        today = datetime.datetime.now(tz=pytz.utc)
        if (today - message.created_at).days <= 30:
            stats[member]["delta"] += 1

    # generate metadata
    for info in stats.values():
        for k in metadata.keys():
            metadata[k] += info[k]

    # Save to CSV
    if save_to_file:
        if not os.path.exists('results'):
            os.makedirs('results')
        
        with open(f"results\\{channel.id}_scraped.csv", mode='w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Author', 'Content', 'Timestamp'])

            # Save messages to CSV
            for message in messages:
                writer.writerow([message.author, message.content, message.created_at])

            #TODO: save stats to CSV as well
    
    print(f"Successfully scraped {len(messages)} messages from {channel.name} ({channel.id})")
    return messages, stats, metadata

async def compile_stats(ctx):
    """
    Compiles cumulative stats for a server, essentially a helper function for below

    Args:
        ctx: context from command (this isn't called directly)

    Returns:
        dict: dict of dicts containing stats per member
            - member: the author
            - dict: stats
                - int: message count
                - delta: message difference
                - chars: character count
        dict: metadata for all messages from all users in the channel
            - int: message count
            - delta: message difference
            - chars: character count 
    """
    print("Compiling stats...")
    # Scrape all (accessible) channels in currentfor message information
    all_stats = {}
    all_metadata = {"count": 0,
                    "delta": 0,
                    "chars": 0}
    channels_counter = 0
    for channel in ctx.guild.text_channels:
        try:
            _, stats, metadata = await scrape_messages(channel, False)
            channels_counter += 1
        except discord.errors.Forbidden:
            print("A Forbidden error occurred (maybe incorrect permissions?) Ask Alex")

        # Combine stat and meta dictionaries
        for member, info in stats.items():
            # Add new member
            if member not in all_stats:
                all_stats[member] = info
            # Accumulate stats
            for k in info.keys():
                all_stats[member][k] += info[k]
        for k in metadata:
            all_metadata[k] += metadata[k]

    # Generate extra data
    for info in all_stats.values():
        info["percent"] = info["count"] / all_metadata["count"] * 100
        info["increase"] = info["delta"] / info["count"] * 100
        info["average"] = info["chars"] / info["count"]

    all_metadata["percent"] = all_metadata["count"] / all_metadata["count"] # Obviously should be 100%
    all_metadata["increase"] = all_metadata["delta"] / all_metadata["count"]
    all_metadata["average"] = all_metadata["chars"] / all_metadata["count"]

    print("Done!")
    return all_stats, all_metadata, channels_counter


@client.command(name="msgstats")
async def print_message_stats(ctx, sortby="count"):
    """
    Utilizes scrape_messages() to find all channel stats

    Args:
        ctx: context from command
    """
    await ctx.send("Generating message stats, hold on...")
    all_stats, all_metadata, channels_counter = await compile_stats(ctx)

    # Compile and send the final stats message
    # Name, count, delta, percent, increase, avg -- but fancy!
    header = ["Name", '\u03A3', "\u0394", "#", "%\u03A3", "%\u2191", "\u0078\u0304"]
    rows = []

    # Sort in descending order  by the sortby parameter (see default above)
    sorted_stats = sorted(all_stats.items(), key=lambda x : x[1][sortby], reverse=True) # crazy one-liner :D
    count = 1
    for member, info in sorted_stats:
        rows.append([f"{count}.", textwrap.shorten(member.name, width=14, placeholder="-"),
                    info['count'], info['delta'], info['chars'], \
                    f"{info['percent']:.1f}%", f"{info['increase']:.1f}%", f"{info['average']:.1f}"])
        count += 1

    # Generate table
    table = tabulate.tabulate(rows, header, floatfmt=".1f")

    # Print all lines as long as <2000 characters
    # Something awkward going on with char_count but don't wanna think about it
    char_count = 0
    subtable = ""
    for line in table.split('\n'):
        # print(line) # comment out later
        char_count += len(line)
        if char_count > 1900: # buffer of 100 chars because it was being weird
            char_count = len(line)
            # print(subtable) # comment out as needed
            await ctx.send("`" + subtable + "`")
            subtable = ""
        subtable += line + '\n'
    await ctx.send("`" + subtable + "`")

    await ctx.send(f"Overall I scraped: {channels_counter} channels and found {all_metadata['count']} messages from {len(all_stats)} unique users")    
    print("Done with message stats!")

@client.command(name="test")
async def test_command(ctx):
    await ctx.send(f"You are currently in: {repr(ctx.guild.name)}")
    _, stats, metadata = await scrape_messages(ctx.channel, False)
    for name, info in stats.items():
        print(name.name)
        print(info)
    print(metadata)

# ===============
# OTHER FUNCTIONS
# ===============

def run():
    """Run the bot"""
    client.run(TOKEN)

# ===========
# Main driver
# ===========

# Probably delete this later
if __name__ == "__main__":
    run()
    
