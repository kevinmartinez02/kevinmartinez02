from collections import Counter
from datetime import datetime, timezone
from functools import lru_cache
from math import cos, pi
import os
from pathlib import Path
import re
from types import MethodType

import gifos
from gifos.utils.convert_ansi_escape import ConvertAnsiEscape
from PIL import Image, ImageDraw
import requests

GREEN = "\x1b[92m"
BLUE = "\x1b[94m"
YELLOW = "\x1b[93m"
CYAN = "\x1b[96m"
MAGENTA = "\x1b[95m"
WHITE = "\x1b[97m"
DIM = "\x1b[90m"
RESET = "\x1b[0m"

# GitHub Dark palette: blends naturally into a profile README.
THEME_BG_TOP = (13, 17, 23)  # canvas.default / #0d1117
THEME_BG_BOTTOM = THEME_BG_TOP
THEME_PANEL = THEME_BG_TOP
THEME_PANEL_ALT = THEME_BG_TOP
THEME_BORDER = (48, 54, 61)  # border.default / #30363d
THEME_CYAN = (88, 166, 255)  # accent.fg / #58a6ff
THEME_PURPLE = (210, 168, 255)
THEME_PINK = (248, 81, 73)
THEME_GREEN = (63, 185, 80)

ConvertAnsiEscape.ANSI_ESCAPE_MAP_TXT_COLOR.update(
    {
        "90": "#8b949e",
        "92": "#56d364",
        "93": "#e3b341",
        "94": "#58a6ff",
        "95": "#d2a8ff",
        "96": "#79c0ff",
        "97": "#f0f6fc",
    }
)

GITHUB_USER = "kevinmartinez02"
AGE = 23
FALLBACK_LOCATION = "Guatemala"
PROFILE_HOLD_SECONDS = 6

PROMPT = f"{GREEN}kevin@github{RESET}:{BLUE}~{RESET}$ "
AVATAR_WAVE_FILES = (
    "assets/kevin-avatar-wave-1.png",
    "assets/kevin-avatar-wave-2.png",
)


def calculate_user_rating(stats: dict[str, str | int | float]) -> str:
    """Create a compact activity rating from the public profile metrics."""
    contributions = int(str(stats["contributions"]).replace(",", ""))
    score = (
        (4 if contributions >= 1000 else 3 if contributions >= 500 else 2)
        + (1 if int(stats["commits"]) >= 50 else 0)
        + (1 if int(stats["public_repos"]) >= 10 else 0)
        + (1 if int(stats["stars"]) >= 10 else 0)
        + (1 if int(stats["pull_requests"]) >= 10 else 0)
    )
    if score >= 8:
        return "A+"
    if score == 7:
        return "A"
    if score == 6:
        return "B+"
    if score == 5:
        return "B"
    if score == 4:
        return "B-"
    return "C+"


def fetch_github_stats() -> dict[str, str | int | float]:
    """Fetch public GitHub stats, with stable fallbacks for offline generation."""
    current_year = datetime.now(timezone.utc).year
    stats: dict[str, str | int | float] = {
        "public_repos": 12,
        "followers": 0,
        "stars": 0,
        "commits": 58,
        "pull_requests": 0,
        "merged_pull_requests": 0,
        "merged_percentage": 0.0,
        "top_languages": "TypeScript, Python, HTML, PHP",
        "contributions": "1,421",
        "contribution_year": current_year,
        "location": FALLBACK_LOCATION,
    }

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "kevinmartinez02-readme-terminal",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        profile_response = requests.get(
            f"https://api.github.com/users/{GITHUB_USER}",
            headers=headers,
            timeout=15,
        )
        profile_response.raise_for_status()
        profile = profile_response.json()

        repos_response = requests.get(
            f"https://api.github.com/users/{GITHUB_USER}/repos",
            headers=headers,
            params={"per_page": 100, "type": "owner"},
            timeout=15,
        )
        repos_response.raise_for_status()
        repos = repos_response.json()

        languages = Counter(repo["language"] for repo in repos if repo.get("language"))
        stats.update(
            {
                "public_repos": profile.get("public_repos", stats["public_repos"]),
                "followers": profile.get("followers", stats["followers"]),
                "stars": sum(repo.get("stargazers_count", 0) for repo in repos),
                "top_languages": (
                    ", ".join(language for language, _ in languages.most_common(4))
                    if languages
                    else stats["top_languages"]
                ),
                "location": profile.get("location") or FALLBACK_LOCATION,
            }
        )

        search_requests = {
            "commits": (
                "https://api.github.com/search/commits",
                (
                    f"author:{GITHUB_USER} "
                    f"committer-date:{current_year}-01-01..{current_year}-12-31"
                ),
            ),
            "pull_requests": (
                "https://api.github.com/search/issues",
                f"type:pr author:{GITHUB_USER}",
            ),
            "merged_pull_requests": (
                "https://api.github.com/search/issues",
                f"type:pr author:{GITHUB_USER} is:merged",
            ),
        }
        for key, (url, query) in search_requests.items():
            response = requests.get(
                url,
                headers=headers,
                params={"q": query, "per_page": 1},
                timeout=15,
            )
            response.raise_for_status()
            stats[key] = response.json().get("total_count", stats[key])

        pull_requests = int(stats["pull_requests"])
        merged_pull_requests = int(stats["merged_pull_requests"])
        stats["merged_percentage"] = (
            round(merged_pull_requests / pull_requests * 100, 1)
            if pull_requests
            else 0.0
        )

        contribution_response = requests.get(
            f"https://github.com/users/{GITHUB_USER}/contributions",
            headers={"User-Agent": headers["User-Agent"]},
            timeout=15,
        )
        contribution_response.raise_for_status()
        contribution_dates = re.findall(
            r'data-date="([^"]+)"',
            contribution_response.text,
        )
        contribution_counts = re.findall(
            r"<tool-tip[^>]*>(No|\d+) contributions?",
            contribution_response.text,
        )
        if len(contribution_dates) == len(contribution_counts):
            contribution_total = sum(
                int(count)
                for date, count in zip(
                    contribution_dates,
                    contribution_counts,
                )
                if date.startswith(f"{current_year}-") and count != "No"
            )
            stats["contributions"] = f"{contribution_total:,}"
    except (requests.RequestException, ValueError, KeyError):
        pass

    stats["user_rating"] = calculate_user_rating(stats)
    return stats


t = gifos.Terminal(750, 500, 15, 15)
t._Terminal__def_bg_color = THEME_PANEL
t._Terminal__bg_color = THEME_PANEL
t._Terminal__frame = Image.new("RGB", (750, 500), THEME_BG_TOP)
t.toggle_show_cursor(True)


def set_theme_bg_color(
    terminal: gifos.Terminal,
    background: tuple[int, int, int] | str | None = None,
) -> None:
    """Make ANSI resets return to the active card instead of library black."""
    terminal._Terminal__bg_color = (
        background
        if background is not None
        else terminal._Terminal__def_bg_color
    )


t.set_bg_color = MethodType(set_theme_bg_color, t)


def put(text: str, row: int, col: int = 1, count: int = 1) -> None:
    """Place text without triggering gifos' single-column scroll behavior."""
    t.gen_text(text, row, col, count, False, True)


def type_at(text: str, row: int, col: int = 1, speed: int = 1) -> None:
    """Type at an exact terminal cell."""
    t._Terminal__col_in_row[row] = col
    t.cursor_to_box(row, col, contin=True)
    t.gen_typing_text(text, row, col, contin=True, speed=speed)


def draw_gradient() -> None:
    """Paint GitHub's exact dark canvas color."""
    draw = ImageDraw.Draw(t._Terminal__frame)
    draw.rectangle((0, 0, 749, 499), fill=THEME_BG_TOP)


def draw_terminal_chrome(title: str, layout: str = "full") -> None:
    """Add a polished frame and content panels to the current scene."""
    draw_gradient()
    draw = ImageDraw.Draw(t._Terminal__frame)

    draw.rounded_rectangle(
        (5, 5, 744, 494),
        radius=13,
        outline=THEME_BORDER,
        width=2,
    )
    draw.rounded_rectangle(
        (14, 8, 735, 39),
        radius=8,
        fill=t._Terminal__def_bg_color,
        outline=THEME_BORDER,
    )
    for x, color in (
        (584, THEME_PINK),
        (601, (227, 179, 65)),
        (618, THEME_GREEN),
    ):
        draw.ellipse((x - 4, 18, x + 4, 26), fill=color)
    draw.text((635, 16), title, fill=(139, 148, 158))

    if layout == "profile":
        draw.rounded_rectangle(
            (22, 68, 263, 340),
            radius=12,
            fill=THEME_PANEL,
            outline=THEME_BORDER,
        )
        draw.rounded_rectangle(
            (269, 48, 727, 455),
            radius=12,
            fill=THEME_PANEL_ALT,
            outline=THEME_BORDER,
        )
    elif layout == "about":
        draw.rounded_rectangle(
            (10, 53, 727, 447),
            radius=14,
            fill=THEME_PANEL,
            outline=THEME_BORDER,
        )
    else:
        draw.rounded_rectangle(
            (10, 48, 727, 462),
            radius=14,
            fill=THEME_PANEL,
            outline=THEME_BORDER,
        )


def reset_screen(title: str, layout: str = "full") -> None:
    """Clear pixels and reset gifos' internal column tracking."""
    scene_background = THEME_PANEL_ALT if layout == "profile" else THEME_PANEL
    t._Terminal__def_bg_color = scene_background
    t._Terminal__bg_color = scene_background
    t.clear_frame()
    for row in range(1, t.num_rows + 1):
        t.delete_row(row)
    draw_terminal_chrome(title, layout)


@lru_cache(maxsize=None)
def load_sprite(image_file: str, size_multiplier: float) -> Image.Image:
    """Load and resize each sprite only once."""
    with Image.open(image_file) as source:
        sprite = source.convert("RGB")
        for corner in (
            (0, 0),
            (sprite.width - 1, 0),
            (0, sprite.height - 1),
            (sprite.width - 1, sprite.height - 1),
        ):
            ImageDraw.floodfill(sprite, corner, THEME_PANEL, thresh=18)
        width = int(source.width * size_multiplier)
        height = int(source.height * size_multiplier)
        return sprite.resize(
            (width, height),
            Image.Resampling.NEAREST,
        )


def draw_sprite_frame(
    sprite: Image.Image,
    row: int,
    col: int,
    y_offset: int = 0,
) -> None:
    """Replace a sprite in-place and record one frame without clearing text."""
    x1, y1, _, _ = t.cursor_to_box(row, col, contin=True, force_col=True)

    padding = 8
    clear_box = Image.new(
        "RGB",
        (sprite.width, sprite.height + padding * 2),
        THEME_PANEL,
    )
    t._Terminal__frame.paste(clear_box, (x1, y1 - padding))
    t._Terminal__frame.paste(sprite, (x1, y1 + y_offset))
    t._Terminal__gen_frame(t._Terminal__frame)


def animate_sprite(
    image_files: tuple[str, ...],
    row: int,
    col: int,
    size_multiplier: float,
    frame_count: int,
    frames_per_pose: int,
    transition_frames: int,
) -> None:
    """Animate smoothly between poses with cosine easing."""
    sprites = tuple(load_sprite(path, size_multiplier) for path in image_files)
    for frame_index in range(frame_count):
        pose_index = (frame_index // frames_per_pose) % len(sprites)
        next_index = (pose_index + 1) % len(sprites)
        frame_in_pose = frame_index % frames_per_pose
        transition_start = max(0, frames_per_pose - transition_frames)
        pose_progress = max(
            0,
            (frame_in_pose - transition_start)
            / max(1, transition_frames - 1),
        )
        eased_progress = (1 - cos(pi * pose_progress)) / 2
        sprite = Image.blend(
            sprites[pose_index],
            sprites[next_index],
            eased_progress,
        )
        draw_sprite_frame(
            sprite,
            row,
            col,
        )


def animate_avatar(seconds: float = 1) -> None:
    animate_sprite(
        AVATAR_WAVE_FILES,
        5,
        3,
        0.175,
        max(1, int(15 * seconds)),
        frames_per_pose=8,
        transition_frames=3,
    )


def make_gif_play_once(file_name: str = "output.gif") -> None:
    """Remove FFmpeg's infinite-loop extension so the logout is the true ending."""
    gif_path = Path(file_name)
    data = gif_path.read_bytes()
    netscape_loop = b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00"
    if netscape_loop in data:
        gif_path.write_bytes(data.replace(netscape_loop, b"", 1))


github = fetch_github_stats()

# Scene 1: BIOS-style boot.
draw_terminal_chrome("BOOT")
put(f"{MAGENTA}KEVIN_OS{RESET} {WHITE}Modular BIOS v2.0.26{RESET}", 1)
put(f"{DIM}Copyright (C) 2026, Kevin Alfredo Martinez{RESET}", 2)
t.clone_frame(10)
put(f"{CYAN}GitHub Profile ReadMe Terminal{RESET}", 4)
put(f"CPU Test.............. {GREEN}OK{RESET}", 6)
t.clone_frame(5)
put(f"Memory Test........... {GREEN}64KB OK{RESET}", 7)
t.clone_frame(5)
put(f"Network Adapter....... {CYAN}ONLINE{RESET}", 8)
t.clone_frame(5)
put(f"Profile Drive......... {MAGENTA}DETECTED{RESET}", 9)
t.clone_frame(12)
put(f"{DIM}Press ENTER to start{RESET} {CYAN}KEVIN OS{RESET}...", 25)
t.clone_frame(20)

# Scene 2: profile, professional summary, and live GitHub stats.
reset_screen("MY PROFILE", "profile")
type_at(f"{PROMPT}fetch.sh -u {GITHUB_USER}", 1)
draw_sprite_frame(load_sprite(AVATAR_WAVE_FILES[0], 0.175), 5, 3)
put(f"{MAGENTA}{GITHUB_USER}{RESET}{CYAN}@GitHub{RESET}", 2, 34)
put(f"{DIM}--------------------------{RESET}", 3, 34)
animate_avatar(0.8)
put(f"{CYAN}Name:{RESET} Kevin Alfredo Martinez", 4, 34)
put(f"{CYAN}Age:{RESET} {AGE}", 5, 34)
put(f"{CYAN}Location:{RESET} {github['location']}", 6, 34)
animate_avatar(0.8)
put(f"{CYAN}Role:{RESET} Full-Stack Developer", 7, 34)
put(f"{CYAN}Focus:{RESET} Meaningful web products", 8, 34)
animate_avatar(0.8)

put(f"{MAGENTA}WHAT I DO{RESET}", 10, 34)
put(f"{DIM}--------{RESET}", 11, 34)
put("I build scalable web apps that turn complex ideas", 12, 34)
put("into secure products with meaningful real-world impact.", 13, 34)
animate_avatar(1)

put(f"{MAGENTA}GITHUB STATS{RESET}", 15, 34)
put(f"{DIM}------------{RESET}", 16, 34)
put(f"{CYAN}User Rating:{RESET} {github['user_rating']}", 17, 34)
animate_avatar(0.5)
put(f"{CYAN}Total Stars Earned:{RESET} {github['stars']}", 18, 34)
animate_avatar(0.5)
put(
    f"{CYAN}Total Commits ({github['contribution_year']}):{RESET} "
    f"{github['commits']}",
    19,
    34,
)
animate_avatar(0.5)
put(f"{CYAN}Total PRs:{RESET} {github['pull_requests']}", 20, 34)
animate_avatar(0.5)
put(
    f"{CYAN}Merged PRs:{RESET} {github['merged_pull_requests']} "
    f"({github['merged_percentage']}%)",
    21,
    34,
)
animate_avatar(0.5)
put(
    f"{CYAN}Contributions ({github['contribution_year']}):{RESET} "
    f"{github['contributions']}",
    22,
    34,
)
animate_avatar(0.5)
put(f"{CYAN}Top Languages:{RESET} {github['top_languages']}", 23, 34)
put(f"{PROMPT}{GREEN}# Profile loaded successfully{RESET}", 25)
animate_avatar(PROFILE_HOLD_SECONDS)

# Scene 3: clear the terminal, log out, and terminate the session.
type_at(f"{PROMPT}clear", 25)
t.clone_frame(8)
reset_screen("SESSION")
type_at(f"{PROMPT}logout", 1)
put(f"{DIM}Saving session history...{RESET}", 3)
t.clone_frame(8)
put(f"{GREEN}[ OK ]{RESET} Profile data synchronized", 5)
t.clone_frame(8)
put(f"{GREEN}[ OK ]{RESET} GitHub connection closed", 6)
t.clone_frame(8)
put("Connection to github.com closed.", 8)
put(f"{MAGENTA}KEVIN OS session terminated.{RESET}", 10)
t.clone_frame(60)

t.gen_gif()
make_gif_play_once()
