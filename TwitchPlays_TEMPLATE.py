import concurrent.futures
import random
import keyboard
import time
import os
import pydirectinput
import requests
import pyautogui
import re
import TwitchPlays_Connection
from gtts import gTTS
from elevenlabs import set_api_key, generate, save, voices, play
from dotenv import load_dotenv
from pygame import mixer
from TwitchPlays_KeyCodes import *

##################### .env VARIABLES #####################

# Load variables from .env file
load_dotenv()

# Access the variables
directory = os.getenv("directory")
filtered_words = os.getenv("filtered_words")

# Elevenlabs set_api_key
api_key = os.getenv("11Labs_API_KEY")
set_api_key(api_key)


##################### GAME VARIABLES #####################

# Replace this with your Twitch username. Must be all lowercase.
TWITCH_CHANNEL = 'itsskylight' 

# If streaming on Youtube, set this to False
STREAMING_ON_TWITCH = True

# If you're streaming on Youtube, replace this with your Youtube's Channel ID
# Find this by clicking your Youtube profile pic -> Settings -> Advanced Settings
YOUTUBE_CHANNEL_ID = "YOUTUBE_CHANNEL_ID_HERE" 

# If you're using an Unlisted stream to test on Youtube, replace "None" below with your stream's URL in quotes.
# Otherwise you can leave this as "None"
YOUTUBE_STREAM_URL = None

##################### MESSAGE QUEUE VARIABLES #####################

# MESSAGE_RATE controls how fast we process incoming Twitch Chat messages. It's the number of seconds it will take to handle all messages in the queue.
# This is used because Twitch delivers messages in "batches", rather than one at a time. So we process the messages over MESSAGE_RATE duration, rather than processing the entire batch at once.
# A smaller number means we go through the message queue faster, but we will run out of messages faster and activity might "stagnate" while waiting for a new batch. 
# A higher number means we go through the queue slower, and messages are more evenly spread out, but delay from the viewers' perspective is higher.
# You can set this to 0 to disable the queue and handle all messages immediately. However, then the wait before another "batch" of messages is more noticeable.
MESSAGE_RATE = 0.5
# MAX_QUEUE_LENGTH limits the number of commands that will be processed in a given "batch" of messages. 
# e.g. if you get a batch of 50 messages, you can choose to only process the first 10 of them and ignore the others.
# This is helpful for games where too many inputs at once can actually hinder the gameplay.
# Setting to ~50 is good for total chaos, ~5-10 is good for 2D platformers
MAX_QUEUE_LENGTH = 20
MAX_WORKERS = 100 # Maximum number of threads you can process at a time 

last_time = time.time()
message_queue = []
thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS)
active_tasks = []
pyautogui.FAILSAFE = False

##########################################################

# Count down before starting, so you have time to load up the game
countdown = 5
while countdown > 0:
    print(countdown)
    countdown -= 1
    time.sleep(1)

if STREAMING_ON_TWITCH:
    t = TwitchPlays_Connection.Twitch()
    t.twitch_connect(TWITCH_CHANNEL)
else:
    t = TwitchPlays_Connection.YouTube()
    t.youtube_connect(YOUTUBE_CHANNEL_ID, YOUTUBE_STREAM_URL)

class Player:
    def __init__(self):
        self.pokemon = ""
        self.username = ""
        self.voice = ""
        self.slot = 0
        self.gender = ""


male_voices = ["Adam", "Antoni", "Arnold", "Josh", "Sam"]
female_voices = ["Domi","Bella","Rachel","Elli"]
queue_users = []
allowed_users = []

def handle_message(message):
    try:
        msg = message['message'].lower()
        username = message['username'].lower()

        print("Got this message from " + username + ": " + msg)

        #If the user types, "!pokemon" add them to the queued users
        if (msg == "!pokemon"):
            adding_pokemon(username)

        #If the user is playing then allow them in
        for user in allowed_users:
            if (user.username == username):
                print(f"Allowed user: {username}")
                #check to see if there is any words
            
                #generate the message
                generate_message(msg, username)
            else:
                print(f"Not allowed user: {username}")

        print(allowed_users)

    except Exception as e:
        print("Encountered exception: " + str(e))

def adding_pokemon(user):
    queue_users.append(user)
    

def every_message_tts(chat_message):
        mytext = chat_message
        # Language in which you want to convert
        language = 'en'
        myobj = gTTS(text=mytext, lang=language, slow=False)
        sanitized_text = re.sub(r'\W+', '', mytext)

        filename = f"{sanitized_text}.mp3"
        filepath = os.path.join(directory,filename)
        
        myobj.save(filepath)

        mixer.init()
        mixer.music.load(filepath)
        mixer.music.play()

def filter_message(message):
    #split the message into words
    words = message.split()

    #Check the words
    for word in words:
        for filtered_word in filtered_words:
            if filtered_word in word:
                return False

    return True

def remove_user_from_slot(slot):
    # case 1: Slot is empty
    found_user = None
    for user in allowed_users:
        if user.slot == slot:
            found_user = user
            break
    
    if found_user is None:
        print(f"Slot {slot} is empty.")
        return 0
    
    if (found_user.gender == "Male"):
        current_voice_M = found_user.voice
        male_voices.append(current_voice_M)
    if (found_user.gender == "Female"):
        current_voice_F = found_user.voice
        female_voices.append(current_voice_F)
        

    # case 2: Slot is full
    # Empty the slot by resetting the attributes of the Player class
    found_user.username = ""
    found_user.pokemon = ""
    found_user.voice = ""
    found_user.gender = ""
    found_user.slot = 0
    allowed_users.remove(found_user)

    # Print a message to indicate the removal
    print(f"User {found_user.username} in slot {slot} removed.")

    # Print a message to indicate the removal
    print(f"User, {user} in slot {slot} removed.")

def add_user_to_slot(slot):
    #Add a random user from chat
    if len(queue_users) == 0:
        print("Empty Queued Users")
    else:
        selected_user = random.choice(queue_users)
        queue_users.remove(selected_user)
        user = Player()
        allowed_users.append(user)

        user.username = selected_user
        user.pokemon = input("Enter Pokemon: ")
        user.gender = input("Enter Gender: Male/Female")
        user.slot = slot

        if (user.gender == "Male"):
            selected_voice_M = random.choice(male_voices)
            male_voices.remove(selected_voice_M)
            user.voice = selected_voice_M
        if (user.gender == "Female"):
            selected_voice_F = random.choice(female_voices)
            female_voices.remove(selected_voice_F)
            user.voice = selected_voice_F

        print(f'{selected_user} in slot {slot} added')

def replace_user(slot):
    remove_user_from_slot(slot)
    add_user_to_slot(slot)

def generate_message(message, username):
    for player in allowed_users:
       if (player.username == username):
           print("Found User")
           pokemon = player.pokemon
           mytext = f'{pokemon} said {message}'
           voice_to_use = player.voice
           if not voice_to_use:   
               every_message_tts(message)
           else:
               audio = generate(
                   text=mytext,
                   voice=voice_to_use,
                   model="eleven_monolingual_v1"
               )
               play(audio)



##################### While True ###########################

# Define the key combinations and their corresponding functions
key_mappings = {
    'ctrl+shift+1': add_user_to_slot,
    'ctrl+shift+2': add_user_to_slot,
    'ctrl+shift+3': add_user_to_slot,
    'ctrl+shift+4': add_user_to_slot,
    'ctrl+shift+5': add_user_to_slot,
    'ctrl+shift+6': add_user_to_slot,
}

remove_user_key_mappings = {
    'ctrl+r+1': remove_user_from_slot,
    'ctrl+r+2': remove_user_from_slot,
    'ctrl+r+3': remove_user_from_slot,
    'ctrl+r+4': remove_user_from_slot,
    'ctrl+r+5': remove_user_from_slot,
    'ctrl+r+6': remove_user_from_slot,
}



while True:
    active_tasks = [t for t in active_tasks if not t.done()]

    # Check for new messages
    new_messages = t.twitch_receive_messages()
    if new_messages:
        message_queue += new_messages
        message_queue = message_queue[-MAX_QUEUE_LENGTH:]

    messages_to_handle = []
    if not message_queue:
        # No messages in the queue
        last_time = time.time()
    else:
        # Determine how many messages we should handle now
        r = 1 if MESSAGE_RATE == 0 else (time.time() - last_time) / MESSAGE_RATE
        n = int(r * len(message_queue))
        if n > 0:
            # Pop the messages we want off the front of the queue
            messages_to_handle = message_queue[0:n]
            del message_queue[0:n]
            last_time = time.time()

    # If user presses Shift+Backspace, automatically end the program
    if keyboard.is_pressed('shift+backspace+ctrl'):
        exit()

    # Check if any of the key combinations are pressed for adding
    for key_combination, action in key_mappings.items():
        if keyboard.is_pressed(key_combination):
            # Extract the slot number from the key combination
            slot_number = int(key_combination[-1])
            action(slot_number)

    # Check if any of the key combinations are pressed for removing
    for remove_user_key_combination, action in remove_user_key_mappings.items():
        if keyboard.is_pressed(remove_user_key_combination):
            # Extract the slot number from the key combination
            slot_number = int(remove_user_key_combination[-1])
            action(slot_number)

    if not messages_to_handle:
        continue
    else:
        for message in messages_to_handle:
            if len(active_tasks) <= MAX_WORKERS:
                active_tasks.append(thread_pool.submit(handle_message, message))
            else:
                print(f'WARNING: active tasks ({len(active_tasks)}) exceeds number of workers ({MAX_WORKERS}). ({len(message_queue)} messages in the queue)')
 
