import time
import discord
from discord.ext import commands
import configparser
import asyncio
from ai import Ai
from datetime import datetime
import pytz  # Importa pytz per il fuso orario
import json  # Importa json per la persistenza dei dati

# Assicurati che la classe Ai abbia il metodo ask
ai = Ai()

# Funzione per caricare i conteggi da un file JSON
def load_submission_counts():
    try:
        with open('form_submission_counts.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

# Funzione per salvare i conteggi in un file JSON
def save_submission_counts():
    with open('form_submission_counts.json', 'w') as f:
        json.dump(form_submission_counts, f)

# Leggere il token dal file config.cfg
config = configparser.ConfigParser()
config.read('config.cfg')

try:
    TOKEN = config.get('DiscordToken', 'token').strip('"')
except (configparser.NoSectionError, configparser.NoOptionError):
    print("Errore: il token non è stato trovato nel file di configurazione.")
    exit(1)

# Leggere le categorie e i ruoli dal file di configurazione
categories = [config.get('Categorie', key).strip('"') for key in config['Categorie']]
roles_to_exclude = [config.get('Ruoli', key).strip('"') for key in config['Ruoli']]

# Dizionario per tracciare il numero di invii del form per canale (caricamento da file JSON)
form_submission_counts = load_submission_counts()

# Inizializzazione del bot con il prefisso di comando '!' e intents.
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

class PersistentView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # View senza timeout

        button = discord.ui.Button(label="Inviami un messaggio", style=discord.ButtonStyle.primary, custom_id="persistent_button")
        self.add_item(button)
        button.callback = self.button_callback  # Aggiungere il callback del pulsante

    async def button_callback(self, interaction: discord.Interaction):
        channel_id = str(interaction.channel.id)

        # Controllare il numero di invii per questo canale
        if form_submission_counts.get(channel_id, 0) >= 2:
            await interaction.response.send_message("Hai raggiunto il limite di richieste per questo ticket.", ephemeral=True)
            return

        class MessageModal(discord.ui.Modal, title="Descrivi il tuo problema"):
            # Impostazione dei limiti di lunghezza del campo di testo
            message_input = discord.ui.TextInput(
                label="Descrizione:",
                style=discord.TextStyle.paragraph,
                min_length=18,  # Minimo 18 caratteri
                max_length=500  # Massimo 500 caratteri
            )

            async def on_submit(self, interaction: discord.Interaction):
                print(f"richiesta: {self.message_input.value}")
                await interaction.response.send_message("Attendi un momento, sto elaborando la tua richiesta...", ephemeral=True)
                response = await asyncio.to_thread(ai.ask, self.message_input.value)
                await interaction.channel.send(response)

                # Incrementa il contatore per il canale
                form_submission_counts[channel_id] = form_submission_counts.get(channel_id, 0) + 1

                # Salva il nuovo conteggio nel file JSON
                save_submission_counts()

        modal = MessageModal()
        await interaction.response.send_modal(modal)

@bot.event
async def on_ready():
    print(f'Il bot è connesso come {bot.user}')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="le vostre domande"))

    # Ricaricare la view persistente
    bot.add_view(PersistentView())
    print("View persistente registrata")

@bot.event
async def on_guild_channel_create(channel):
    print(f'Canale creato: {channel.name} (Categoria: {channel.category_id})')
    if channel.category and str(channel.category.id) in categories:
        print(f'Il canale {channel.name} è in una categoria monitorata.')

        allowed_members = []
        special_members = []  # Per tenere traccia dei membri con ruoli speciali
        for member in channel.guild.members:
            if member == bot.user:
                continue
            if any(str(role.id) in roles_to_exclude for role in member.roles):
                special_members.append(member)  # Membro con ruolo escluso
            else:
                # Solo se non ha i ruoli esclusi
                if channel.permissions_for(member).read_messages:
                    allowed_members.append(member)

        # Ora controlla se ci sono allowed_members (quelli da pingare)
        if allowed_members:
            # Usa il saluto con il ping degli utenti
            member_mentions = ', '.join(member.mention for member in allowed_members)
            description = f"Ciao {member_mentions}, sono N.O.V.A. e posso assisterti in assenza di uno staffer umano. Puoi chiedermi delle informazioni o sottopormi un problema da risolvere. Premi il pulsante qua sotto per iniziare."
        else:
            # Se nessuno da pingare, usa il saluto senza mention
            description = f"Ciao, sono N.O.V.A. e posso assisterti in assenza di uno staffer umano. Puoi chiedermi delle informazioni o sottopormi un problema da risolvere. Premi il pulsante qua sotto per iniziare."

        # Crea l'embed
        embed = discord.Embed(
            title="N.O.V.A.",
            description=description,
            color=0xD81E02  # Colore in formato esadecimale
        )
        # Modifica il footer con il timestamp e l'icona
        embed.set_footer(
            text="N.O.V.A.",
            icon_url="https://www.scarletmc.it/Logo%20NOVA.png"
        )

        # Ottieni il timestamp con il fuso orario Europe/Rome
        rome_tz = pytz.timezone('Europe/Rome')
        embed.timestamp = datetime.now(rome_tz)  # Imposta il timestamp con il fuso orario corretto

        time.sleep(6)

        message = await channel.send(embed=embed)

        # Usa la view persistente
        await message.edit(view=PersistentView())

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return  # Ignora i messaggi inviati dal bot stesso

    role_id_to_check = 1287737364101468194

    # Controlla se il bot è stato menzionato o se il ruolo con ID specifico è stato menzionato
    if bot.user in message.mentions or any(role.id == role_id_to_check for role in message.role_mentions):
        user_mention = message.author.mention

        if message.channel.category and str(message.channel.category.id) in categories:
            # Se il canale appartiene a una delle categorie specificate
            await message.channel.send(f"Ciao {user_mention}, se hai bisogno di aiuto puoi premere il pulsante e sottopormi una domanda o un problema. Se non dovessi riuscire ad aiutari aspetta l'assistenza di uno staffer umano, grazie della pazienza.")
        else:
            # Se il canale non appartiene a una delle categorie specificate
            await message.channel.send(f"Ciao {user_mention}, se hai bisogno di aiuto ti consiglio di aprire un ticket nella sezione https://discord.com/channels/702962544796762182/996098908470136903, in questo modo io e il resto dello staff potremmo aiutarti.")

    await bot.process_commands(message)  # Assicura che i comandi del bot funzionino correttamente

bot.run(TOKEN)
