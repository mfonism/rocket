import random
import re
import datetime
from collections import defaultdict
import logging
import asyncio

import rctogether
from bot import Bot

logging.basicConfig(level=logging.INFO)

ANIMALS = [
    {"emoji": "🐕", "name": "dog", "noise": "woof!"},
    {"emoji": "🐈", "name": "cat", "noise": "miaow!"},
    {"emoji": "🐁", "name": "mouse", "noise": "squeak!"},
    {"emoji": "🦛", "name": "hippo"},
    {"emoji": "🐸", "name": "frog", "noise": "ribbet!"},
    {"emoji": "🦖", "name": "t-rex", "noise": "RAWR!"},
    {"emoji": "🦜", "name": "parrot", "noise": "HELLO!"},
    {"emoji": "🐊", "name": "crocodile"},
    {"emoji": "🦒", "name": "giraffe"},
    {"emoji": "🦆", "name": "duck", "noise": "quack!"},
    {"emoji": "🐑", "name": "sheep", "noise": "baa!"},
    {"emoji": "🐢", "name": "turtle"},
    {"emoji": "🐘", "name": "elephant"},
    {"emoji": "🦉", "name": "owl", "noise": "hoot hoot!"},
    {"emoji": "🐉", "name": "dragon", "noise": "🔥"},
    {"emoji": "🚀", "name": "rocket"},
    {"emoji": "🦊", "name": "fox", "noise": "Wrahh!"},
    {"emoji": "🦄", "name": "unicorn", "noise": "✨"},
    {"emoji": "🦔", "name": "hedgehog", "noise": "scurry, scurry, scurry"},
    {"emoji": "🦕", "name": "brontosaurus", "noise": "MEEEHHH!"},
    {"emoji": "🐌", "name": "snail", "noise": "slurp!"},
    {"emoji": "🐫", "name": "camel"},
    {"emoji": "🐇", "name": "rabbit"},
    {"emoji": "🐛", "name": "caterpillar", "noise": "munch!"},
    {"emoji": "🦙", "name": "llama"},
    {"emoji": "🦀", "name": "crab", "noise": "click!"},
    {"emoji": "🦘", "name": "kangaroo", "noise": "Chortle chortle!"},
    {"emoji": "🦇", "name": "bat", "noise": "screech!"},
    {"emoji": "🐄", "name": "cow", "noise": "Moo!"},
]

NOISES = {animal["emoji"]: animal.get("noise", "💖") for animal in ANIMALS}

GENIE_HOME = {"x": 60, "y": 15}
SPAWN_POINTS = [
    {"x": 58, "y": 15},
    {"x": 58, "y": 13},
    {"x": 60, "y": 13},
    {"x": 62, "y": 13},
    {"x": 62, "y": 15},
    {"x": 62, "y": 17},
    {"x": 60, "y": 17},
]

SAD_MESSAGES = [
    "Was I not a good %(animal_name)s?",
    "I thought you liked me.",
    "😢",
    "What will I do now?",
    "But where will I go?",
    "One day I might learn to trust again...",
    "I only wanted to make you happy.",
    "My heart hurts.",
    "Did I do something wrong?",
    "But why?",
    "💔",
]

MANNERS = [
    "please",
    "bitte",
    "le do thoil",
    "sudo",
    "per favore",
    "oh mighty djinn",
    "s'il vous plaît",
    "s'il vous plait",
    "svp",
    "por favor",
    "kudasai",
    "onegai shimasu",
]


def sad_message(animal_name):
    return random.choice(SAD_MESSAGES) % {"animal_name": animal_name}


def a_an(noun):
    if noun[0] in "AaEeIiOoUu":
        return "an " + noun
    return "a " + noun


def position_tuple(pos):
    return (pos["x"], pos["y"])


def response_handler(commands, pattern):
    def handler(f):
        commands.append((pattern, f))
        return f

    return handler


def reset_agency():
    for bot in rctogether.get_bots():
        if bot["emoji"] == "🧞":
            pass
        elif not bot.get("message"):
            rctogether.delete_bot(bot["id"])


class Agency:
    COMMANDS = []

    def __init__(self, session, genie, available_animals, owned_animals):
        self.session = session
        self.genie = genie
        self.available_animals = available_animals
        self.owned_animals = owned_animals
        self.processed_message_dt = datetime.datetime.utcnow()


    @classmethod
    async def create(cls, session):
        genie = None
        available_animals = {}
        owned_animals = defaultdict(list)

        for bot_json in await rctogether.bots.get(session):
            bot = Bot(bot_json)
            bot.start_task(session)

            if bot_json["emoji"] == "🧞":
                print("Found the genie!")
                genie = bot
            else:
                if bot_json.get("message"):
                    owner_id = bot_json["message"]["mentioned_entity_ids"][0]
                    owned_animals[owner_id].append(bot)
                else:
                    available_animals[position_tuple(bot_json["pos"])] = bot

        agency = cls(session, genie, available_animals, owned_animals)
        return agency

    async def restock_inventory(self):
        if not self.genie:
            self.genie = await Bot.create(
                self.session,
                name="Pet Agency Genie",
                emoji="🧞",
                x=GENIE_HOME["x"],
                y=GENIE_HOME["y"],
                can_be_mentioned=True,
            )

        for pos in SPAWN_POINTS:
            if position_tuple(pos) not in self.available_animals:
                self.available_animals[position_tuple(pos)] = await self.spawn_animal(pos)

    async def spawn_animal(self, pos):
        animal = random.choice(ANIMALS)
        while self.available(animal["emoji"]):
            animal = random.choice(ANIMALS)

        return await Bot.create(
            self.session,
            name=animal["name"],
            emoji=animal["emoji"],
            x=pos["x"],
            y=pos["y"],
        )

    def available(self, animal):
        return any(x.emoji == animal for x in self.available_animals.values())

    def get_by_name(self, animal_name):
        for animal in self.available_animals.values():
            if animal.name == animal_name:
                return animal
        return None

    def pop_owned_by_type(self, animal_name, owner):
        for animal in self.owned_animals[owner["id"]]:
            if animal.name.split(" ")[-1] == animal_name:
                self.owned_animals[owner["id"]].remove(animal)
                return animal
        return None

    def random_available_animal(self):
        return random.choice(list(self.available_animals.values()))

    def random_owned(self, owner):
        return random.choice(self.owned_animals[owner["id"]])

    async def send_message(self, recipient, message_text, sender=None):
        sender = sender or self.genie
        await rctogether.messages.send(self.session, sender.id, f"@**{recipient['person_name']}** {message_text}")

    @response_handler(COMMANDS, "time to restock")
    async def handle_restock(self, adopter, match):
        await self.restock_inventory()
        return "New pets now in stock!"

    @response_handler(COMMANDS, "adopt (a|an|the|one)? ([A-Za-z-]+)")
    async def handle_adoption(self, adopter, match):
        if not any(please in match.string.lower() for please in MANNERS):
            return "No please? Our pets are only available to polite homes."

        animal_name = match.groups()[1]

        if animal_name == "horse":
            return "Sorry, that's just a picture of a horse."

        if animal_name == "genie":
            return "You can't adopt me. I'm not a pet!"

        if animal_name == "apatosaurus":
            return "Since 2015 the brontasaurus and apatosaurus have been recognised as separate species. Would you like to adopt a brontasaurus?"

        animal = self.get_by_name(animal_name)

        if not animal:
            alternative = self.random_available_animal().name
            return f"Sorry, we don't have {a_an(animal_name)} at the moment, perhaps you'd like {a_an(alternative)} instead?"

        await self.send_message(adopter, NOISES.get(animal.emoji, "💖"), animal)
        await rctogether.bots.update(
            self.session,
            animal.id,
            {"name": f"{adopter['person_name']}'s {animal.name}"}
        )
        del self.available_animals[position_tuple(animal.bot_json["pos"])]
        self.owned_animals[adopter["id"]].append(animal)

        return None

    @response_handler(COMMANDS, "thank")
    async def handle_thanks(self, adopter, match):
        return random.choice(["You're welcome!", "No problem!", "❤️"])

    @response_handler(COMMANDS, r"abandon my ([A-Za-z-]+)")
    async def handle_abandonment(self, adopter, match):
        animal_name = match.groups()[0]
        animal = self.pop_owned_by_type(animal_name, adopter)

        if not animal:
            suggested_alternative = self.random_owned(adopter).name.split(" ")[-1]
            return f"Sorry, you don't have {a_an(animal_name)}. Would you like to abandon your {suggested_alternative} instead?"

        await self.send_message(adopter, sad_message(animal_name), animal)
        await rctogether.bots.delete(self.session, animal.id)
        return None

    @response_handler(
        COMMANDS, r"well[- ]actually|feigning surprise|backseat driving|subtle[- ]*ism"
    )
    async def handle_social_rules(self, adopter, match):
        return "Oh, you're right. Sorry!"

    async def handle_mention(self, adopter, message):
        for (pattern, handler) in self.COMMANDS:
            match = re.search(pattern, message["text"], re.IGNORECASE)
            if match:
                response = await handler(self, adopter, match)
                if response:
                    await self.send_message(adopter, response)
                return

        await self.send_message(
            adopter, "Sorry, I don't understand. Would you like to adopt a pet?"
        )

    async def handle_entity(self, entity):
        if entity["type"] == "Avatar":
            message = entity.get("message")

            if message and self.genie.id in message["mentioned_entity_ids"]:
                message_dt = datetime.datetime.strptime(
                    message["sent_at"], "%Y-%m-%dT%H:%M:%SZ"
                )
                if message_dt <= self.processed_message_dt:
                    print("Skipping old message: ", message)
                else:
                    await self.handle_mention(entity, message)
                    self.processed_message_dt = message_dt

        if entity["type"] == "Avatar":
            for animal in self.owned_animals.get(entity["id"], []):
                print(entity)
                position = offset_position(entity["pos"], random.choice(DELTAS))
                print(f"Moving {animal} to {position}")
                await animal.update(position)


DELTAS = [{"x": x, "y": y} for x in [-1, 0, 1] for y in [-1, 0, 1] if x != 0 or y != 0]


def offset_position(position, delta):
    return {"x": position["x"] + delta["x"], "y": position["y"] + delta["y"]}


async def main():
    async with rctogether.RestApiSession() as session:
        agency = await Agency.create(session)

        async for entity in rctogether.WebsocketSubscription():
            await agency.handle_entity(entity)


if __name__ == "__main__":
    asyncio.run(main())
