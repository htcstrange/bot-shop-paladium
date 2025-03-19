import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import asyncio
import json
import os

TOTO = ""

debug = True
SERVER = True
intents = discord.Intents().all()

class PersistentViewBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=commands.when_mentioned_or('/'), help_command=None, case_insensitive=True, intents=intents)

    async def setup_hook(self) -> None:
        views = [ShopView()]
        for element in views:
            self.add_view(element)
            
bot = PersistentViewBot()

@bot.command()
async def sync(ctx):
    synced = await ctx.bot.tree.sync()
    server = bot.guilds[0]
    member_count = server.member_count
    await bot.change_presence(status=discord.Status.dnd, activity=discord.Activity(type=discord.ActivityType.watching, name=f"{member_count} membres"))
    await ctx.send(f"Synced {len(synced)} commands")

def run_bot(token=TOTO, debug=False):
    if debug: 
        print(bot._connection.loop)
    bot.run(token)
    if debug: 
        print(bot._connection.loop)
    return bot._connection.loop.is_closed()
    
tree = bot.tree

CATEGORY_ID = 1149352504765714482
LOG_CHANNEL_ID = 949768557187702804

COMMANDS_FILE = 'commandes.json'
ONGOING_FILE = 'commandesencours.json'

class ShopView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ShopButton())

class ShopButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Commander", emoji="\U0001F6D2", style=discord.ButtonStyle.primary, custom_id="shop_order_button")

    async def callback(self, interaction: discord.Interaction):
        modal = ShopModal(interaction.user, interaction.channel.id)
        await interaction.response.send_modal(modal)

class ShopModal(discord.ui.Modal):
    def __init__(self, user: discord.Member, shop_channel_id: int):
        super().__init__(title="Formulaire de Commande")
        self.user = user
        self.shop_channel_id = shop_channel_id

        self.add_item(discord.ui.TextInput(label="Votre pseudo sur Paladium ?", required=True))
        self.add_item(discord.ui.TextInput(label="Quel item voulez-vous ?", required=True))
        self.add_item(discord.ui.TextInput(label="Combien en voulez-vous ?", required=True))
        self.add_item(discord.ui.TextInput(label="Combien cela coûte-t-il ?", required=True))
        self.add_item(discord.ui.TextInput(label="Délais de livraison souhaités ?", required=True))

    async def on_submit(self, interaction: discord.Interaction):
        pseudo = self.children[0].value
        item = self.children[1].value
        quantity = self.children[2].value
        price = self.children[3].value
        delay = self.children[4].value

        with open("commandes.json", "r") as f:
            commandes = json.load(f)

        commandes[str(interaction.user.id)] = {
            "pseudo": pseudo,
            "item": item,
            "quantity": quantity,
            "price": price,
            "delay": delay
        }

        with open("commandes.json", "w") as f:
            json.dump(commandes, f, indent=4)

        guild = interaction.guild
        category = discord.utils.get(guild.categories, id=CATEGORY_ID)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        channel = await category.create_text_channel(
            f"🛒 commande-{interaction.user.display_name}", overwrites=overwrites
        )

        embed = discord.Embed(
            title=f"Commande de {pseudo}",
            description=(f"{get_emoji('shop')} **Item :** {item}\n{get_emoji('flecheRose')} **Quantité :** {quantity}\n{get_emoji('Dollar')}**Prix :** {price}\n {get_emoji('server')}**Délais :** {delay}"),
            color=0x242079
        )
        embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/263/263142.png")

        view = OrderView(interaction.user.id)
        message = await channel.send(embed=embed, view=view)

        try:
            with open("commandesencours.json", "r") as f:
                commandes_encours = json.load(f)
        except FileNotFoundError:
            commandes_encours = {}

        commandes_encours[str(interaction.user.id)] = {
            "channel_id": channel.id,
            "message_id": message.id,
            "user_id": interaction.user.id
        }

        with open("commandesencours.json", "w") as f:
            json.dump(commandes_encours, f, indent=4)

        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            embed=create_small_embed(f"{get_emoji('Ticket')} Commande créée par {interaction.user.mention} dans {channel.mention}.")
            await log_channel.send(embed=embed)

class OrderView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.add_item(CancelButton(user_id))
        self.add_item(FinishButton(user_id))
        self.add_item(TakeButton(user_id)) 

class CancelButton(discord.ui.Button):
    def __init__(self, user_id):
        super().__init__(label="Annuler", style=discord.ButtonStyle.danger, custom_id="cancel_button")
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            embed = create_small_embed(f"{get_emooji('no')} Vous n'êtes pas autorisé à annuler cette commande.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed=create_small_embed(f"Le ticket sera supprimé dans 3 secondes {get_emoji('load')}")
        await interaction.response.send_message(embed=embed)
        await asyncio.sleep(3)

        await interaction.channel.delete()

        with open("commandes.json", "r") as f:
            commandes = json.load(f)
        commandes.pop(str(self.user_id), None)
        with open("commandes.json", "w") as f:
            json.dump(commandes, f, indent=4)

        with open("commandesencours.json", "r") as f:
            commandes_encours = json.load(f)
        commandes_encours.pop(str(self.user_id), None)
        with open("commandesencours.json", "w") as f:
            json.dump(commandes_encours, f, indent=4)

        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            embed=create_small_embed(f"{get_emoji('check_black')} Commande annulée par {interaction.user.mention}.")
            await log_channel.send(embed=embed)

class FinishButton(discord.ui.Button):
    def __init__(self, user_id):
        super().__init__(label="Finir", style=discord.ButtonStyle.success, custom_id="finish_button")
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id == self.user_id:
            embed = create_small_embed(f"{get_emoji('no')} Vous ne pouvez pas terminer votre propre commande.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed=create_small_embed(f"Le ticket sera supprimé dans 3 secondes {get_emoji('load')}")
        await interaction.response.send_message(embed=embed)
        await asyncio.sleep(3)
        await interaction.channel.delete()

        with open("commandes.json", "r") as f:
            commandes = json.load(f)
        commandes.pop(str(self.user_id), None)
        with open("commandes.json", "w") as f:
            json.dump(commandes, f, indent=4)

        with open("commandesencours.json", "r") as f:
            commandes_encours = json.load(f)
        commandes_encours.pop(str(self.user_id), None)
        with open("commandesencours.json", "w") as f:
            json.dump(commandes_encours, f, indent=4)

        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            embed=create_small_embed(f"{get_emoji('yes')} Commande annulée par {interaction.user.mention}.")
            await log_channel.send(embed=embed)

class TakeButton(discord.ui.Button):
    def __init__(self, user_id):
        super().__init__(label="Prendre", style=discord.ButtonStyle.primary, custom_id="take_button")
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id == self.user_id:
            embed = create_small_embed(f"{get_emoji('no')} Vous ne pouvez pas prendre votre propre commande.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        with open("commandesencours.json", "r") as f:
            commandes_encours = json.load(f)

        commande = commandes_encours.get(str(self.user_id))
        if not commande:
            embed=create_small_embed(f"{get_emoji('error')} Commande introuvable ou déjà prise.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        channel = interaction.channel
        message_id = commande["message_id"]
        try:
            message = await channel.fetch_message(message_id)
            embed = message.embeds[0]
            embed.set_footer(text=f"{interaction.user.display_name} a pris la commande.")
            await message.edit(embed=embed)
        except Exception as e:
            await interaction.response.send_message(f"Erreur : {e}", ephemeral=True)
            return

        commande["taken_by"] = interaction.user.id
        with open("commandesencours.json", "w") as f:
            json.dump(commandes_encours, f, indent=4)

        for child in self.view.children:
            if isinstance(child, TakeButton):
                child.disabled = True
        await interaction.response.edit_message(view=self.view)
        embed=create_small_embed(f"{interaction.user.mention} a pris la commande. {get_emoji('shop')}")
        await interaction.channel.send(embed=embed)

@bot.tree.command()
@discord.app_commands.checks.has_permissions(administrator=True)
async def shop(interaction):
    embed = discord.Embed(
        title=":shopping_cart: Boutique",
        description=f"Cliquez sur le bouton ci-dessous pour passer une commande {get_emoji('shop')}",
        color=0x1A1786
    )
    embed.set_footer(text="Dionysos Shop à votre service !")
    embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/263/263142.png")
    view = ShopView()
    await interaction.response.send_message(embed=embed, view=view)

@bot.event
async def on_command_error(interaction, error):
    if isinstance(error, commands.MissingPermissions):
        await interaction.response.send_message("Désolé, vous n'avez pas la permission d'exécuter cette commande.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await interaction.response.send_message("Il manque des arguments à la commande. Vérifiez la syntaxe.")
    else:
        await interaction.response.send_message("Une erreur s'est produite.")

        
@bot.event
async def on_ready():
    print(f"Bot connecté en tant que {bot.user}")
    try:
        with open("commandesencours.json", "r") as f:
            commandes_encours = json.load(f)
    except FileNotFoundError:
        commandes_encours = {}

    for command in commandes_encours.values():
        user_id = command["user_id"]
        channel_id = command["channel_id"]
        message_id = command["message_id"]

        bot.add_view(OrderView(user_id))

        channel = bot.get_channel(channel_id)
        if channel:
            try:
                await channel.fetch_message(message_id)
                print(f"Vue recréée pour la commande {user_id}")
            except discord.NotFound:
                print(f"Message ou channel introuvable pour la commande {user_id}, suppression des données.")
                del commandes_encours[str(user_id)]

    with open("commandesencours.json", "w") as f:
        json.dump(commandes_encours, f, indent=4)

    print("Toutes les commandes en cours ont été chargées.")


@bot.tree.command()
@discord.app_commands.checks.has_permissions(administrator=True)
async def list_emoji(interaction: discord.Interaction):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("Cette commande doit être utilisée dans un serveur.")
        return

    emojis = guild.emojis
    if not emojis:
        await interaction.response.send_message("Aucun émoji trouvé dans ce serveur.")
        return

    emoji_lines = [f'{emoji} : \\{emoji}' for emoji in emojis]

    MAX_LENGTH = 2000
    chunks = []
    current_chunk = ""
    for line in emoji_lines:
        if len(current_chunk) + len(line) + 1 > MAX_LENGTH:
            chunks.append(current_chunk)
            current_chunk = line + "\n"
        else:
            current_chunk += line + "\n"
    if current_chunk:
        chunks.append(current_chunk)

    await interaction.response.send_message(chunks[0])
    for chunk in chunks[1:]:
        await interaction.followup.send(chunk)

def create_small_embed(description=None, color=0x060270):
	embed = discord.Embed(
		description=description,
		color=color
	)
	return embed

def load_emojis(filename='emojis.json'):
    with open(filename, 'r') as file:
        return json.load(file)

emojis = load_emojis()

def get_emoji(name):
    return emojis.get(name, '')

if SERVER:
    run_bot()
else:
    bot.run(TOTO)