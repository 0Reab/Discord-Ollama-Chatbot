# libs
import os
import json
import logging
import asyncio
import nextcord
import random as r

from nextcord.ext import commands
from openai import OpenAI


discord_token = 'Your Token here' # Change this - token
openai_api_key = "api key" # Change this api key default - ollama
del_time = 300

client = OpenAI(
    api_key=openai_api_key,
    base_url="http://localhost:11434/v1"  # Change this - URL where your ollama is hosted
)


def gif(data) -> str | None:
    dog_url = 'link to dog gif url' # implement random int for gif num
    cat_url =  '--||--'

    dog_lst = ['cat', 'kitty', 'meow']
    cat_lst = ['dog', 'puppy', 'bark']

    if r.randint(0, 1): # roll 50/50 chance for gif
        for keyword in data.split():
            if keyword in dog_lst: return dog_url
            elif keyword in cat_lst: return cat_url


model = "your ollama model here"  # Change this
valid_models = ["llava", "llama3", "llama2"]  # Modify this list to the available models

# File to store conversation history
history_file = os.path.join(os.path.dirname(__file__), 'conversation_histories.json')

# Dictionary to store conversation history
conversation_histories = {}

# Load conversation history from file if it exists
if os.path.exists(history_file):
    print(f"{history_file} found! Loading conversation history from file.")
    try:
        with open(history_file, 'r') as file:
            conversation_histories = json.load(file)
    except json.JSONDecodeError:
        print("Error loading JSON file. File may be corrupted.")


# Function to save conversation history to file
def save_conversation_history():
    try:
        with open(history_file, 'w') as file:
            json.dump(conversation_histories, file, indent=4)
    except Exception as e:
        logging.error(f"Error while saving conversation history: {e}")


# Function to get the bot's nickname
async def get_bot_nickname(guild):
    if guild:
        bot_member = guild.get_member(bot.user.id)
        return bot_member.nick if bot_member.nick else bot.user.name
    else:
        return bot.user.name


# Helper function to split long messages
def split_message(content, max_length=2000):
    return [content[i:i + max_length] for i in range(0, len(content), max_length)]


# Basic self knowladge so the model knows about itself and features. You can add as many as you please
self_knowladge = [
    {"role": "system", "content": "helpful Ai assistant"},
]


# Function to handle chat interactions with OpenAI
async def handle_chat(message):
    user_message = message.content.strip()
    display_name = message.author.global_name
    user_id = message.author.id
    global conversation_histories
    bot_nick = await get_bot_nickname(message.guild)

    # Initialize conversation history for the user if not already present
    if str(user_id) not in conversation_histories:
        conversation_histories[str(user_id)] = []

    # Append the user's message to the conversation history
    conversation_histories[str(user_id)].append({"role": "user", "content": user_message})

    # Prepare the message list for the API Request
    messages = [{"role": "system",
                 "content": f"You are a ai assistant and your name is {bot_nick}."}]
    messages.extend(self_knowladge)
    messages.extend(conversation_histories[str(user_id)])

    # Make API Request
    try:
        async with message.channel.typing():
            response = client.chat.completions.create(
                model=model,
                messages=messages
            )
            chat_response = response.choices[0].message.content

        # Split long messages and send them in chunks. This is a fallback, and should be avoided. Use a system prompt to tell the AI it's limit is 2000 characters.
        for chunk in split_message(chat_response):
            await message.channel.send(chunk, delete_after=del_time)

        # Append the bot's response to the conversation history
        conversation_histories[str(user_id)].append({"role": "assistant", "content": chat_response})

        # Gifs
        send_gif = gif(chat_response)
        if send_gif:
            await asyncio.sleep(0.2)
            await message.channel.send(send_gif, delete_after=del_time)

        # Save the conversation history to file
        save_conversation_history()

    except Exception as e:
        logging.error(f"Error while handling chat: {e}")
        await message.reply("Sorry, something went wrong.")


# Initialize Discord client
intents = nextcord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return  # Ignore messages sent by the bot itself

    if message.content:
        await handle_chat(message)
        return

    # Check if the message is a reply to the bot
    if message.reference:
        replied_message = await message.channel.fetch_message(message.reference.message_id)
        if replied_message.author == bot.user:
            await handle_chat(message)
            return

    # Check if the bot is mentioned in the message
    if bot.user in message.mentions:
        await handle_chat(message)
        return

    await bot.process_commands(message)


async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You do not have permission to use this command.")
    else:
        # Handle other errors (optional)
        raise error  # Re-raise the error for further handling (if needed)


@bot.slash_command(name='clear_all_history', description='Clear all the conversation history')
async def clear_all_history(ctx):
    global conversation_histories
    if ctx.guild:
        if ctx.user.guild_permissions.administrator:
            conversation_histories = {}
            save_conversation_history()
            await ctx.send("All conversation history cleared.")
            print("All conversation history cleared.")
            return
        else:
            await ctx.response.send_message("You are not authorized to run this command.", ephemeral=True)
            return
    else:
        await ctx.send("This command cannot be used in DMs", ephemeral=True)
        return


@bot.slash_command(name='change_model', description='Change the ollama model used by the bot.')
async def change_model(ctx, model_name: str):
    global model
    if ctx.guild:
        if ctx.user.guild_permissions.administrator:
            if model_name not in valid_models:
                await ctx.response.send_message(
                    f"Not valid model named {model_name}. Valid Models are **{', '.join(valid_models)}**",
                    ephemeral=True)
                return
            else:
                model = model_name
                await ctx.send(f"Model changed to **{model_name}**")
                print(f"Model changed to {model_name}")
                return
        else:
            await ctx.response.send_message("You are not authorized to run this command.", ephemeral=True)
            return
    else:
        await ctx.send("This command cannot be used in DMs", ephemeral=True)
        return


@bot.slash_command(name='clear_history', description='Clears the history of the current user')
async def clear_history(interaction: nextcord.Interaction):
    user_id = interaction.user.id
    global conversation_histories
    # Check if the user ID exists in the conversation histories
    if str(user_id) in conversation_histories and conversation_histories[str(user_id)]:
        # Clear the history for the current user
        conversation_histories[str(user_id)] = []
        save_conversation_history()  # Save the updated history to file
        await interaction.response.send_message(f"Your conversation history has been cleared.")
        print(f"Conversation history cleared for user ID {user_id}.")
        return
    else:
        await interaction.response.send_message("You have no conversation history to clear.")
        return


@bot.slash_command(name="list_models", description='Lists the models that can used with the bot.')
async def list_models(ctx):
    await ctx.response.send_message(f"Available Models: **{', '.join(valid_models)}**", ephemeral=True)


@bot.slash_command(name='current_model', description='Lists the current running ollama model')
async def current_model(ctx):
    await ctx.response.send_message(f"The current running model is **{model}**", ephemeral=True)


# Start the Discord bot
bot.run(discord_token)