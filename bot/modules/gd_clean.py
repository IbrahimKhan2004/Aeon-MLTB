from bot.core.config_manager import Config
from bot.helper.ext_utils.bot_utils import new_task, sync_to_async
from bot.helper.ext_utils.links_utils import is_gdrive_id, is_gdrive_link
from bot.helper.ext_utils.status_utils import get_readable_file_size
from bot.helper.mirror_leech_utils.gdrive_utils.clean import GoogleDriveClean
from bot.helper.mirror_leech_utils.gdrive_utils.count import GoogleDriveCount
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.telegram_helper.message_utils import (
    auto_delete_message,
    edit_message,
    send_message,
)

clean_tasks = {}


@new_task
async def driveclean(_, message):
    args = message.text.split()
    if len(args) > 1:
        link = args[1].strip()
    elif reply_to := message.reply_to_message:
        link = reply_to.text.split(maxsplit=1)[0].strip()
    else:
        gdrive_id = Config.GDRIVE_ID
        link = f"https://drive.google.com/drive/folders/{gdrive_id}" if gdrive_id else ""

    if not link:
        return await send_message(
            message,
            "Send GDrive link or ID along with command or by replying to the link/ID by command",
        )

    if is_gdrive_id(link):
        link = f"https://drive.google.com/drive/folders/{link}"

    if not is_gdrive_link(link):
        return await send_message(message, "No GDrive Link Provided")

    clean_msg = await send_message(
        message,
        f"<i>Fetching information for:</i>\n<code>{link}</code>",
    )
    user_id = message.from_user.id if message.from_user else message.sender_chat.id
    gd = GoogleDriveCount()
    res = await sync_to_async(gd.count, link, user_id)

    if res[1] is None:
        return await edit_message(clean_msg, res[0])

    name, mime_type, size, files, folders = res

    try:
        drive_id = gd.get_id_from_url(link, user_id)
    except Exception:
        return await edit_message(
            clean_msg,
            "Google Drive ID could not be found in the provided link",
        )

    buttons = ButtonMaker()
    buttons.data_button("Move to Bin", f"gdclean confirm {drive_id} trash")
    buttons.data_button("Permanent Clean", f"gdclean confirm {drive_id} permanent")
    buttons.data_button("Stop GDrive Clean", "gdclean stop", "footer")

    text = f"⌬ <b><i>GDrive Clean/Trash :</i></b>\n\n"
    text += f"┎ <b>Name:</b> {name}\n"
    text += f"┃ <b>Size:</b> {get_readable_file_size(size)}\n"
    text += f"┖ <b>Files:</b> {files} | <b>Folders:</b> {folders}\n\n"
    text += "<b>NOTES:</b>\n"
    text += "<i>1. All files are permanently deleted if Permanent Del, not moved to trash.\n"
    text += "2. Folder doesn't gets Deleted.\n"
    text += "3. Delete files of custom folder via giving link along with cmd, but it should have delete permissions.\n"
    text += "4. Move to Bin Moves all your files to trash but can be restored again if have permissions.</i>\n\n"
    text += "<code>Choose the Required Action below to Clean your Drive!</code>"

    await edit_message(clean_msg, text, buttons.build_menu(2))


@new_task
async def drivecleancb(_, query):
    message = query.message
    user_id = query.from_user.id
    data = query.data.split()
    if user_id != Config.OWNER_ID:
        await query.answer(text="Not Owner!", show_alert=True)
        return

    if data[1] == "confirm":
        await query.answer()
        drive_id = data[2]
        action = data[3]
        buttons = ButtonMaker()
        if action == "trash":
            buttons.data_button("Confirm Yes", f"gdclean clear {drive_id} trash")
            text = f"Are you sure you want to move all files in this folder to Bin?\n\nID: <code>{drive_id}</code>"
        else:
            buttons.data_button("Confirm Yes", f"gdclean clear {drive_id} permanent")
            text = f"Are you sure? This action is IRREVERSIBLE!\n\nID: <code>{drive_id}</code>"
        buttons.data_button("Back/No", f"gdclean back {drive_id}")
        await edit_message(message, text, buttons.build_menu(2))

    elif data[1] == "back":
        await query.answer()
        await edit_message(message, "<i>Fetching again ...</i>")
        drive_id = data[2]
        gd = GoogleDriveCount()
        res = await sync_to_async(gd.count, drive_id, user_id)
        if res[1] is None:
            return await edit_message(message, res[0])
        name, mime_type, size, files, folders = res
        buttons = ButtonMaker()
        buttons.data_button("Move to Bin", f"gdclean confirm {drive_id} trash")
        buttons.data_button("Permanent Clean", f"gdclean confirm {drive_id} permanent")
        buttons.data_button("Stop GDrive Clean", "gdclean stop", "footer")

        text = f"⌬ <b><i>GDrive Clean/Trash :</i></b>\n\n"
        text += f"┎ <b>Name:</b> {name}\n"
        text += f"┃ <b>Size:</b> {get_readable_file_size(size)}\n"
        text += f"┖ <b>Files:</b> {files} | <b>Folders:</b> {folders}\n\n"
        text += "<b>NOTES:</b>\n"
        text += "<i>1. All files are permanently deleted if Permanent Del, not moved to trash.\n"
        text += "2. Folder doesn't gets Deleted.\n"
        text += "3. Delete files of custom folder via giving link along with cmd, but it should have delete permissions.\n"
        text += "4. Move to Bin Moves all your files to trash but can be restored again if have permissions.</i>\n\n"
        text += "<code>Choose the Required Action below to Clean your Drive!</code>"

        await edit_message(message, text, buttons.build_menu(2))

    elif data[1] == "clear":
        await query.answer()
        trash = data[3] == "trash"
        drive_id = data[2]
        buttons = ButtonMaker()
        buttons.data_button("Stop GDrive Clean", "gdclean stop")
        await edit_message(
            message,
            f"<i>Processing Drive Clean / Trash...</i>\n\nID: <code>{drive_id}</code>",
            buttons.build_menu(1),
        )
        drive = GoogleDriveClean()
        clean_tasks[message.id] = drive
        msg = await sync_to_async(drive.drive_clean, drive_id, user_id, trash=trash)
        clean_tasks.pop(message.id, None)
        await edit_message(message, msg)

    elif data[1] == "stop":
        await query.answer()
        if message.id in clean_tasks:
            clean_tasks[message.id].is_cancelled = True
            await edit_message(message, "⌬ <b>DriveClean Stop Requested!</b>")
        else:
            await edit_message(message, "⌬ <b>DriveClean Stopped!</b>")
            await auto_delete_message(message)
