import sys
import datetime
import asyncio
import traceback
import json

import discord
from discord.ext import commands
import requests
import markovify

import checks

with open('settings.json') as settings_file:
    settings = json.load(settings_file)


# Application info
username = settings["discord"]["description"]
version = settings["discord"]["version"]
print('{} - {}'.format(username, version))
start_time = datetime.datetime.utcnow()


bot = commands.Bot(
    command_prefix=settings["discord"]["command_prefix"],
    description=settings["discord"]["description"]
)

# Remove default help command so we can customise
#bot.remove_command('help')

@checks.admin_or_permissions(manage_server=True)
@bot.command(pass_context=True, name="restart")
async def bot_restart(ctx):
    try:
        print("Bot rebooted by {}".format(ctx.message.author.name))
        await bot.send_message(ctx.message.channel,
            '{} is restarting...'.format(username))
        await asyncio.sleep(2)
        await bot.logout()
        await asyncio.sleep(3)
        await bot.close()
        sys.exit(0)
    except Exception as e:
        print('bot_restart : ', e)
        pass
        sys.exit(0)


@checks.admin_or_permissions(manage_server=True)
@bot.command(pass_context=True, name="ping")
async def bot_ping(ctx):
    pong_message = await bot.say("Pong!")
    await asyncio.sleep(0.5)
    delta = pong_message.timestamp - ctx.message.timestamp
    millis = delta.days * 24 * 60 * 60 * 1000
    millis += delta.seconds * 1000
    millis += delta.microseconds / 1000
    await bot.edit_message(pong_message, "Pong! `{}ms`".format(int(millis)))


def get_bot_uptime(*, brief=False):
    now = datetime.datetime.utcnow()
    delta = now - start_time
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    days, hours = divmod(hours, 24)
    if not brief:
        if days:
            fmt = '{d} days, {h} hours, {m} minutes, and {s} seconds'
        else:
            fmt = '{h} hours, {m} minutes, and {s} seconds'
    else:
        fmt = '{h}h {m}m {s}s'
        if days:
            fmt = '{d}d ' + fmt
    return fmt.format(d=days, h=hours, m=minutes, s=seconds)


@checks.admin_or_permissions(manage_server=True)
@bot.command(pass_context=True, name="status")
async def bot_status(ctx):
    passed = get_bot_uptime()
    lastStarted=start_time.strftime("%b %d, %Y at %I:%M:%S %p UTC")

    lastStartedField = EmbedField(name="Last Started:", value=lastStarted, inline=False)
    uptimeField = EmbedField(name="Uptime:", value=passed, inline=False)
    versionField = EmbedField(name="Version:", value=version, inline=False)
    fieldList = [lastStartedField, uptimeField, versionField]

    embed = embedInformation(title="Bot Status", fieldList=fieldList)
    await bot.say(embed=embed)

@bot.event
async def on_command_error(error, ctx):
    if isinstance(error, commands.errors.CommandNotFound):
        pass  # ...don't need to know if commands don't exist
    if isinstance(error, commands.errors.CheckFailure):
        await bot.send_message(
            ctx.message.channel,
            '{} You don''t have permission to use this command.' \
            .format(ctx.message.author.mention))
    elif isinstance(error, commands.errors.MissingRequiredArgument):
        formatter = commands.formatter.HelpFormatter()
        await bot.send_message(ctx.message.channel,
            '{} You are missing required arguments.\n{}'. \
            format(ctx.message.author.mention,
                formatter.format_help_for(ctx, ctx.command)[0]))
    elif isinstance(error, commands.errors.CommandOnCooldown):
        try:
            await bot.delete_message(ctx.message)
        except discord.errors.NotFound:
            pass
        message = await bot.send_message(
            ctx.message.channel, '{} This command was used {:.2f}s ago ' \
            'and is on cooldown. Try again in {:.2f}s.' \
            .format(ctx.message.author.mention,
                    error.cooldown.per - error.retry_after,
                    error.retry_after))
        await asyncio.sleep(10)
        await bot.delete_message(message)
    else:
        await bot.send_message(ctx.message.channel,
            'An error occured while processing the `{}` command.' \
            .format(ctx.command.name))
        print('Ignoring exception in command {0.command} ' \
            'in {0.message.channel}'.format(ctx))
        tb = traceback.format_exception(type(error), error, error.__traceback__)
        print(''.join(tb))


@bot.event
async def on_error(event_method, *args, **kwargs):
    if isinstance(args[0], commands.errors.CommandNotFound):
        # for some reason runs despite the above
        return
    print('Ignoring exception in {}'.format(event_method))
    mods_msg = "Exception occured in {}".format(event_method)
    tb = traceback.format_exc()
    print(''.join(tb))
    mods_msg += '\n```' + ''.join(tb) + '\n```'
    mods_msg += '\nargs: `{}`\n\nkwargs: `{}`'.format(args, kwargs)
    print(mods_msg)
    print(args)
    print(kwargs)


@bot.event
async def on_ready():
    await asyncio.sleep(1)
    print("Logged in to discord.")
    try:
        await bot.change_presence(
            game=discord.Game(name=settings["discord"]["game"]),
            status=discord.Status.online,
            afk=False)
    except Exception as e:
        print('on_ready : ', e)
        pass
    await asyncio.sleep(1)


@bot.command(pass_context=True, name='markov')
async def markov(ctx):
    if ctx.message.author == bot.user:
        return
    argument = ctx.message.content.split(' ', 3)[1]
    state_size = ''
    try:
        state_size = ctx.message.content.split(' ', 3)[2]
    except:
        pass
    url = 'https://www.reddit.com/user/{0}/comments/.json?limit=100&sort=new'.format(argument)
    headers = {'User-agent': '{} - {}'.format(username, version)}
    r = requests.get(url, headers=headers)
    raw = r.json()
    try:
        if str(raw['message']).lower() == "not found":
            await bot.say('{0.author.mention} {1}'.format(ctx.message, 'User not found.'))
            return
    except:
        pass
    comments = []
    for item in raw['data']['children']:
        try:
            comments.append(str(item['data']['body']))
        except:
            pass
    corpus = '\n\n'.join(comments)
    text_model = markovify.Text(corpus)
    reply = ''
    if state_size:
        sentence = text_model.make_sentence(tries=100, max_overlap_ratio=0.6, state_size=int(state_size))
    else:
        sentence = text_model.make_sentence(tries=100, max_overlap_ratio=0.6)
    if sentence:
        reply = '{0.author.mention} {1}'.format(ctx.message, sentence)
        await bot.say(reply)
    else:
        await bot.say('{0.author.mention} {1}'.format(ctx.message, 'Unable to build text chain.'))
    await asyncio.sleep(2)



bot.run(settings["discord"]["client_token"])
