# form_plugin.py
from discord.ext import commands
from discord import ui, Modal, TextInput, Interaction
from motor.motor_asyncio import AsyncIOMotorCollection

class FormModal(Modal):
    def __init__(self, form_name, db_collection: AsyncIOMotorCollection):
        super().__init__(title="Create a new form")
        self.form_name = form_name
        self.db_collection = db_collection
        self.title_input = TextInput(label="Form Title", placeholder="Enter the form title")
        self.option_input = TextInput(label="Form Options", style=TextInput.Style.paragraph, placeholder="Enter form options separated by commas")

        # Add inputs to modal
        self.add_item(self.title_input)
        self.add_item(self.option_input)

    async def on_submit(self, interaction: Interaction):
        form_data = {
            "form_name": self.form_name,
            "title": self.title_input.value,
            "options": [option.strip() for option in self.option_input.value.split(",")]
        }
        # Insert form data into the MongoDB collection
        await self.db_collection.update_one({"form_name": self.form_name}, {"$set": form_data}, upsert=True)
        await interaction.response.send_message(f"Form '{self.form_name}' created and saved successfully!", ephemeral=True)

    async def on_error(self, interaction: Interaction, error: Exception):
        await interaction.response.send_message(f"An error occurred: {error}", ephemeral=True)

    async def on_timeout(self):
        print("Modal creation timed out")

class FormPlugin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.coll = bot.api.get_plugin_partition(self)  # Get the MongoDB collection for this plugin

    @commands.command(name='form_create')
    async def form_create(self, ctx, form_name: str):
        """Creates a form with a Discord modal."""
        modal = FormModal(form_name, self.coll)
        await ctx.send_modal(modal)

    @commands.command(name='form_send')
    async def form_send(self, ctx, form_name: str):
        """Sends a form to a user in a ModMail thread."""
        form = await self.coll.find_one({"form_name": form_name})
        if not form:
            await ctx.send(f"Form '{form_name}' not found!")
            return

        class FormResponseModal(Modal):
            def __init__(self, form_data):
                super().__init__(title=form_data["title"])
                self.form_data = form_data
                self.responses = {}
                for option in form_data["options"]:
                    self.add_item(TextInput(label=option, placeholder=f"Enter response for {option}"))

            async def on_submit(self, interaction: Interaction):
                # Collect all the responses
                for child in self.children:
                    self.responses[child.label] = child.value
                
                # Send the filled out form back to the ModMail thread
                responses_text = "\n".join([f"**{q}:** {a}" for q, a in self.responses.items()])
                await interaction.response.send_message(f"Form response:\n{responses_text}", ephemeral=True)
                
                # Send to modmail thread
                modmail_thread = ctx.channel
                await modmail_thread.send(f"**Form Response:**\n{responses_text}")

            async def on_timeout(self):
                await ctx.send("The form timed out. Please try again later.")

            async def on_error(self, interaction: Interaction, error: Exception):
                await interaction.response.send_message(f"An error occurred: {error}", ephemeral=True)

        # Send the form modal to the user
        response_modal = FormResponseModal(form)
        await ctx.send_modal(response_modal)

async def setup(bot):
    await bot.add_cog(FormPlugin(bot))
