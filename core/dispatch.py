from collections.abc import Awaitable, Callable

import discord

_CommandHandler = Callable[[discord.Message], Awaitable[None]]


def register_command(
    bot: discord.Client,
    prefix: str,
    handler: _CommandHandler,
) -> None:
    """Register a prefix-to-handler mapping on the given bot.

    A single ``on_message`` listener is attached per bot instance; subsequent
    calls only mutate the per-bot registry. The listener iterates the registry
    and awaits the first handler whose prefix matches
    ``message.content.startswith(prefix)``. Messages authored by ``bot.user``
    are ignored. Unmatched messages return silently.
    """
    registry: dict[str, _CommandHandler] = getattr(bot, "_command_registry", None) or {}
    if not hasattr(bot, "_command_registry"):
        bot._command_registry = registry  # type: ignore[attr-defined]
    registry[prefix] = handler

    if getattr(bot, "_command_dispatcher_installed", False):
        return

    @bot.event
    async def on_message(message: discord.Message) -> None:
        if message.author == bot.user:
            return
        current_registry: dict[str, _CommandHandler] = getattr(
            bot, "_command_registry", {}
        )
        for registered_prefix, registered_handler in current_registry.items():
            if message.content.startswith(registered_prefix):
                await registered_handler(message)
                return

    bot._command_dispatcher_installed = True  # type: ignore[attr-defined]
