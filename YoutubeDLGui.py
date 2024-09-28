from customtkinter import *
from pytubefix import YouTube
from PIL import Image
import requests
from io import BytesIO
from pytubefix.exceptions import *
import pathlib
from CTkMessagebox import CTkMessagebox
from tkinter import filedialog
import threading
from moviepy.editor import VideoFileClip, AudioFileClip
import os
import time

set_appearance_mode("System")
set_default_color_theme("blue")

CURRENT_PATH = pathlib.Path().resolve()
YT = None  # Initialize globally
progress_value = 0  # Initialize progress value globally
current_process = ""  # New variable to track the current process


def show_error_message(title, message):
    CTkMessagebox(title=title, message=message, icon="cancel")
    return_to_first_ui()  # Return to the first UI after error


def fetch_video_info():
    global YT
    URL = LINK_ENTRY.get()
    
    try:
        YT = YouTube(URL)
        hide_first_ui()
        draw_second_ui()
    except (RegexMatchError, AgeRestrictedError, LoginRequired, AttributeError, VideoPrivate, VideoUnavailable) as e:
        show_error_message("Error", f'The link {URL} is {str(e).lower()}.')
    except Exception as e:
        show_error_message("Error", f"Unexpected error: {str(e)}")


def browse_location():
    DOWNLOAD_LOCATION = filedialog.askdirectory(initialdir=CURRENT_PATH, title="SAVE")
    DOWNLOAD_PATH.set(DOWNLOAD_LOCATION)


def hide_first_ui():
    """Hides the first UI components to make room for the second UI."""
    HEAD_LABEL.grid_forget()
    LINK_ENTRY.grid_forget()
    DESTINATION_ENTRY.grid_forget()
    BROWSE_BUTTON.place_forget()
    FETCH_BUTTON.grid_forget()


def return_to_first_ui():
    """Clears the second UI and returns to the first UI after an error."""
    if 'IMAGE_LABEL' in globals():
        IMAGE_LABEL.grid_forget()
    if 'THUMBNAILTEXT_LABEL' in globals():
        THUMBNAILTEXT_LABEL.grid_forget()
    if 'RESOLUTION_DROPDOWN' in globals():
        RESOLUTION_DROPDOWN.grid_forget()
    if 'DOWNLOAD_BUTTON' in globals():
        DOWNLOAD_BUTTON.grid_forget()
    if 'PROGRESS_BAR' in globals():
        PROGRESS_BAR.grid_forget()
    if 'PERCENTAGE_LABEL' in globals():
        PERCENTAGE_LABEL.grid_forget()

    LINK_ENTRY.delete(0, 'end')  # Clear the link entry field
    DOWNLOAD_PATH.set(CURRENT_PATH)  # Reset the download path
    show_first_ui()


def show_first_ui():
    """Displays the first UI elements."""
    HEAD_LABEL.grid(row=0, column=1, pady=10, padx=5, columnspan=3)
    LINK_ENTRY.grid(row=1, column=1, padx=20, pady=5)
    DESTINATION_ENTRY.grid(row=2, column=1, padx=20, pady=5)
    BROWSE_BUTTON.place(x=540, y=120)
    FETCH_BUTTON.grid(row=3, column=1, padx=20, pady=10)


def draw_second_ui():
    global YT

    # Show the video thumbnail
    response = requests.get(YT.thumbnail_url)
    img = Image.open(BytesIO(response.content))
    thumbnail_image = CTkImage(img, size=(350, 200))

    global IMAGE_LABEL
    IMAGE_LABEL = CTkLabel(gui, text="", image=thumbnail_image)
    IMAGE_LABEL.grid(row=0, column=1)

    # Show the video title
    global THUMBNAILTEXT_LABEL
    THUMBNAILTEXT_LABEL = CTkLabel(gui, text=YT.title)
    THUMBNAILTEXT_LABEL.grid(row=1, column=1)

    # Populate available resolutions (both progressive and DASH streams)
    resolutions = sorted(
        set(int(stream.resolution[:-1]) for stream in YT.streams.filter(file_extension='mp4', type="video") if stream.resolution)
    )

    # Create a dropdown for available resolutions
    global RESOLUTION_DROPDOWN
    RESOLUTION_DROPDOWN = CTkOptionMenu(gui, values=[f"{res}p" for res in resolutions], width=300)
    RESOLUTION_DROPDOWN.grid(row=2, column=1, padx=20, pady=5)
    RESOLUTION_DROPDOWN.set(f"{resolutions[0]}p")  # Set default to the lowest resolution

    # Create a download button
    global DOWNLOAD_BUTTON
    DOWNLOAD_BUTTON = CTkButton(gui, text="Download", command=start_download_thread)
    DOWNLOAD_BUTTON.grid(row=3, column=1, padx=20, pady=10)

    # Create a progress bar
    global PROGRESS_BAR
    PROGRESS_BAR = CTkProgressBar(gui, width=300)
    PROGRESS_BAR.set(0)  # Set progress to 0
    PROGRESS_BAR.grid(row=4, column=1, padx=20, pady=5)

    # Create a label to show download percentage and process
    global PERCENTAGE_LABEL
    PERCENTAGE_LABEL = CTkLabel(gui, text="0% - Ready to download")
    PERCENTAGE_LABEL.grid(row=5, column=1)


def download_progress(stream, chunk, bytes_remaining):
    global progress_value, current_process
    total_size = stream.filesize
    downloaded_size = total_size - bytes_remaining
    progress_value = downloaded_size / total_size * 0.5  # Progress up to 50%
    current_process = "Downloading video and audio"
    update_progress_bar()

def update_progress_bar():
    PROGRESS_BAR.set(progress_value)
    percentage = int(progress_value * 100)
    PERCENTAGE_LABEL.configure(text=f"{percentage}% - {current_process}")
    gui.update_idletasks()  # Force update of the GUI

def monitor_merge_progress(output_path, video_size, audio_size):
    global progress_value, current_process
    total_size = video_size + audio_size
    start_time = time.time()
    current_process = "Merging video and audio"
    while progress_value < 0.99:  # Changed from 1 to 0.99 to avoid overshooting
        if os.path.exists(output_path):
            current_size = os.path.getsize(output_path)
            new_progress = 0.5 + (current_size / total_size) * 0.5
            progress_value = min(new_progress, 0.99)  # Ensure we don't exceed 99%
            update_progress_bar()
        time.sleep(0.1)  # Update every 100ms
        
        # Add a timeout to prevent infinite loop
        if time.time() - start_time > 600:  # 10 minutes timeout
            break


def merge_progress(current_time, total_time):
    global progress_value
    progress_value = 0.5 + (current_time / total_time) * 0.5  # Progress from 50% to 100%
    update_progress_bar()


def start_download_thread():
    """Starts a new thread to download the video without freezing the UI."""
    download_thread = threading.Thread(target=download_video)
    download_thread.start()


def download_video():
    global YT, progress_value, current_process
    try:
        selected_resolution = RESOLUTION_DROPDOWN.get()
        
        video_stream = YT.streams.filter(res=selected_resolution, file_extension='mp4').first()
        audio_stream = YT.streams.filter(only_audio=True).first()

        if video_stream and audio_stream:
            YT.register_on_progress_callback(download_progress)

            video_path = pathlib.Path(DOWNLOAD_PATH.get()) / "Video.mp4"
            audio_path = pathlib.Path(DOWNLOAD_PATH.get()) / "Audio.mp4"

            current_process = "Downloading video"
            video_stream.download(output_path=DOWNLOAD_PATH.get(), filename="Video.mp4")
            
            current_process = "Downloading audio"
            audio_stream.download(output_path=DOWNLOAD_PATH.get(), filename="Audio.mp4")

            # Reset progress for merging phase
            progress_value = 0.5
            current_process = "Preparing to merge"
            update_progress_bar()

            merge_video_audio(video_path, audio_path)

            CTkMessagebox(title="Success", message="Download and merge complete", icon="check")
        else:
            show_error_message("Error", f"Resolution {selected_resolution} or audio not available.")
    except Exception as e:
        show_error_message("Error", f"An error occurred while downloading: {str(e)}")

def merge_video_audio(video_path, audio_path):
    global current_process
    try:
        video_clip = VideoFileClip(str(video_path))
        audio_clip = AudioFileClip(str(audio_path))
        final_clip = video_clip.set_audio(audio_clip)
        final_output_path = video_path.parent / "Final_Video.mp4"
        
        # Start progress monitoring thread
        video_size = os.path.getsize(video_path)
        audio_size = os.path.getsize(audio_path)
        progress_thread = threading.Thread(target=monitor_merge_progress, 
                                           args=(str(final_output_path), video_size, audio_size))
        progress_thread.start()

        # Write the final video file
        current_process = "Merging video and audio"
        final_clip.write_videofile(str(final_output_path), 
                                   codec="libx264", 
                                   audio_codec="aac")

        # Wait for the progress thread to finish
        progress_thread.join()

        # Ensure progress reaches 100%
        global progress_value
        progress_value = 1.0
        current_process = "Download and merge complete"
        update_progress_bar()

        video_clip.close()
        audio_clip.close()
        final_clip.close()

        video_path.unlink()
        audio_path.unlink()
    except Exception as e:
        show_error_message("Error", f"An error occurred while merging video and audio: {str(e)}")


def main():
    global gui, LINK_ENTRY, HEAD_LABEL, DESTINATION_ENTRY, BROWSE_BUTTON, FETCH_BUTTON, DOWNLOAD_PATH

    gui = CTk()  # Main window created first
    gui.title("YoutubeDL GUI")
    gui.geometry("720x480")
    gui.grid_columnconfigure(1, weight=1)
    gui.resizable(False, False)

    DOWNLOAD_PATH = StringVar()  # Create StringVar after main window is initialized

    # UI ELEMENTS (First UI)
    global HEAD_LABEL, LINK_ENTRY, DESTINATION_ENTRY, BROWSE_BUTTON, FETCH_BUTTON
    HEAD_LABEL = CTkLabel(gui, text="YouTubePy", padx=15, pady=15)
    LINK_ENTRY = CTkEntry(gui, placeholder_text="Enter Your YouTube Link", height=35, width=350)
    DESTINATION_ENTRY = CTkEntry(gui, textvariable=DOWNLOAD_PATH, height=35, width=350)
    DESTINATION_ENTRY.insert(0, CURRENT_PATH)
    BROWSE_BUTTON = CTkButton(gui, text="Browse", command=browse_location, width=20, height=25)
    FETCH_BUTTON = CTkButton(gui, text="Fetch Resolutions", command=fetch_video_info)

    show_first_ui()
    gui.mainloop()


if __name__ == "__main__":
    main()