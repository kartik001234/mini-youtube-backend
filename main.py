from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
import os
import shutil
import subprocess
import uuid
import hashlib

app = FastAPI()

UPLOAD_FOLDER = "videos"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.mount("/videos", StaticFiles(directory="videos"), name="videos")


def calculate_hash(file_path, first_mb_only=True):
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        if first_mb_only:
            h.update(f.read(5*1024*1024))  # first 5MB
        else:
            for chunk in iter(lambda: f.read(4096), b""):
                h.update(chunk)
    return h.hexdigest()


@app.get("/", response_class=HTMLResponse)
def home():
    videos = os.listdir(UPLOAD_FOLDER)
    videos.sort(reverse=True)

    video_cards = ""

    for video_id in videos:
        video_folder = os.path.join(UPLOAD_FOLDER, video_id)

        title_file = os.path.join(video_folder, "title.txt")
        views_file = os.path.join(video_folder, "views.txt")
        thumbnail_path = f"/videos/{video_id}/thumbnail.jpg"

        # Title
        if os.path.exists(title_file):
            with open(title_file, "r") as f:
                title = f.read()
        else:
            title = "No Title"

        # Views
        if os.path.exists(views_file):
            with open(views_file, "r") as f:
                views = f.read()
        else:
            views = "0"

        video_cards += f"""
        <div style="margin:20px; display:inline-block;">
            <a href="/watch/{video_id}" style="color:white; text-decoration:none;">
                <img src="{thumbnail_path}" width="300"><br>
                <b>{title}</b><br>
                👁 {views} views
            </a>
            <br>
            <a href="/delete/{video_id}" style="color:red;">Delete</a>
        </div>
        """

    return f"""
    <html>
        <body style="background:black; color:white; text-align:center;">
            <h1>Mini YouTube</h1>
            <a href="/upload_page" style="color:yellow;">Upload New Video</a>
            <hr>
            {video_cards if video_cards else "<p>No videos uploaded yet</p>"}
        </body>
    </html>
    """


@app.get("/delete/{video_id}")
def delete_video(video_id: str):
    video_folder = os.path.join(UPLOAD_FOLDER, video_id)
    if os.path.exists(video_folder):
        shutil.rmtree(video_folder)
    return RedirectResponse("/", status_code=302)


@app.get("/upload_page", response_class=HTMLResponse)
def upload_page():
    return """
    <html>
        <body style="background:black; color:white; text-align:center;">
            <h2>Upload Video</h2>
            <form action="/upload/" enctype="multipart/form-data" method="post">
                <input type="text" name="title" placeholder="Enter Title" required><br><br>
                <input type="file" name="file" required><br><br>
                <button type="submit">Upload</button>
            </form>
        </body>
    </html>
    """


@app.post("/upload/", response_class=HTMLResponse)
async def upload_video(title: str = Form(...), file: UploadFile = File(...)):
    temp_path = "temp_upload_file"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Calculate hash of full file (safer)
    new_hash = calculate_hash(temp_path, first_mb_only=False)

    # Check for duplicates
    for video_id in os.listdir(UPLOAD_FOLDER):
        video_folder = os.path.join(UPLOAD_FOLDER, video_id)
        hash_file = os.path.join(video_folder, "hash.txt")
        if os.path.exists(hash_file):
            with open(hash_file, "r") as f:
                existing_hash = f.read()
            if existing_hash == new_hash:
                os.remove(temp_path)
                return f"""
                <html>
                    <body style="background:black; color:white; text-align:center;">
                        <h2>Duplicate Video Detected! Upload Aborted.</h2>
                        <a href="/upload_page" style="color:yellow;">Back</a>
                    </body>
                </html>
                """

    # No duplicate → new video folder
    video_id = str(uuid.uuid4())
    video_folder = os.path.join(UPLOAD_FOLDER, video_id)
    os.makedirs(video_folder, exist_ok=True)

    original_path = os.path.join(video_folder, "original.mp4")
    shutil.move(temp_path, original_path)

    # Save title & hash
    with open(os.path.join(video_folder, "title.txt"), "w") as f:
        f.write(title)
    with open(os.path.join(video_folder, "hash.txt"), "w") as f:
        f.write(new_hash)

    # Initialize views & IP tracking
    with open(os.path.join(video_folder, "views.txt"), "w") as f:
        f.write("0")
    open(os.path.join(video_folder, "views_ip.txt"), "a").close()

    # Generate 360p & 720p + thumbnail
    cleaned_path = os.path.join(video_folder, "clean.mp4")

    subprocess.run([
        "ffmpeg", "-i", original_path,
        "-map_metadata", "-1",
        "-c:v", "libx264",
        "-c:a", "aac",
        cleaned_path
    ])

    subprocess.run([
        "ffmpeg", "-i", cleaned_path,
        "-vf", "scale=640:360",
        os.path.join(video_folder, "360p.mp4")
    ])

    subprocess.run([
        "ffmpeg", "-i", cleaned_path,
        "-vf", "scale=1280:720",
        os.path.join(video_folder, "720p.mp4")
    ])

    subprocess.run([
        "ffmpeg", "-i", cleaned_path,
        "-ss", "00:00:01",
        "-vframes", "1",
        os.path.join(video_folder, "thumbnail.jpg")
    ])

    return """
    <html>
        <body style="background:black; color:white; text-align:center;">
            <h2>Upload Successful</h2>
            <a href="/">Go to Home</a>
        </body>
    </html>
    """

    # New video id
    video_id = str(uuid.uuid4())
    video_folder = os.path.join(UPLOAD_FOLDER, video_id)
    os.makedirs(video_folder, exist_ok=True)

    original_path = os.path.join(video_folder, "original.mp4")
    shutil.move(temp_path, original_path)

    # Save title
    with open(os.path.join(video_folder, "title.txt"), "w") as f:
        f.write(title)

    # Save hash
    with open(os.path.join(video_folder, "hash.txt"), "w") as f:
        f.write(new_hash)

    # Initialize views & IP tracking
    with open(os.path.join(video_folder, "views.txt"), "w") as f:
        f.write("0")
    open(os.path.join(video_folder, "views_ip.txt"), "a").close()

    cleaned_path = os.path.join(video_folder, "clean.mp4")

    subprocess.run([
        "ffmpeg", "-i", original_path,
        "-map_metadata", "-1",
        "-c:v", "libx264",
        "-c:a", "aac",
        cleaned_path
    ])

    subprocess.run([
        "ffmpeg", "-i", cleaned_path,
        "-vf", "scale=640:360",
        os.path.join(video_folder, "360p.mp4")
    ])

    subprocess.run([
        "ffmpeg", "-i", cleaned_path,
        "-vf", "scale=1280:720",
        os.path.join(video_folder, "720p.mp4")
    ])

    subprocess.run([
        "ffmpeg", "-i", cleaned_path,
        "-ss", "00:00:01",
        "-vframes", "1",
        os.path.join(video_folder, "thumbnail.jpg")
    ])

    return """
    <html>
        <body style="background:black; color:white; text-align:center;">
            <h2>Upload Successful</h2>
            <a href="/">Go to Home</a>
        </body>
    </html>
    """


@app.get("/watch/{video_id}", response_class=HTMLResponse)
def watch_video(video_id: str, request: Request):

    video_folder = os.path.join(UPLOAD_FOLDER, video_id)
    title_file = os.path.join(video_folder, "title.txt")
    views_file = os.path.join(video_folder, "views.txt")
    views_ip_file = os.path.join(video_folder, "views_ip.txt")

    user_ip = request.client.host

    # Read IPs
    if not os.path.exists(views_ip_file):
        open(views_ip_file, "a").close()

    with open(views_ip_file, "r") as f:
        ips = [line.strip() for line in f.readlines()]

    # Unique view logic
    if user_ip not in ips:
        ips.append(user_ip)
        with open(views_ip_file, "w") as f:
            for ip in ips:
                f.write(ip + "\n")
        # Update view count
        if os.path.exists(views_file):
            with open(views_file, "r") as f:
                views = int(f.read())
            views += 1
            with open(views_file, "w") as f:
                f.write(str(views))
        else:
            with open(views_file, "w") as f:
                f.write("1")
    else:
        if os.path.exists(views_file):
            with open(views_file, "r") as f:
                views = int(f.read())
        else:
            views = 0

    # Title
    if os.path.exists(title_file):
        with open(title_file, "r") as f:
            title = f.read()
    else:
        title = "No Title"

    return f"""
    <html>
        <body style="background:black; color:white; text-align:center;">
            <h2>{title}</h2>
            <p>👁 {views} views</p>

            <video width="800" controls>
                <source src="/videos/{video_id}/360p.mp4" type="video/mp4">
            </video>

            <br><br>
            <a href="/" style="color:yellow;">Back to Home</a>
        </body>
    </html>
    """