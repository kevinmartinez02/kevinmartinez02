from dataclasses import dataclass
from functools import lru_cache
from math import cos, pi, sin
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont


OUTPUT_FILE = Path("claude-profile.gif")

WIDTH = 750
HEIGHT = 500
FPS = 12
DURATION_SECONDS = 42
FRAME_COUNT = FPS * DURATION_SECONDS

BACKGROUND = (13, 17, 23)
PANEL = (22, 27, 34)
PANEL_DEEP = (16, 20, 26)
BORDER = (48, 54, 61)
TEXT = (240, 246, 252)
MUTED = (139, 148, 158)
TERRACOTTA = (204, 120, 92)
TERRACOTTA_BRIGHT = (222, 139, 108)
BLUE = (88, 166, 255)
GREEN = (63, 185, 80)
PURPLE = (210, 168, 255)

HEADER_BOX = (14, 14, WIDTH - 15, 70)
VIEWPORT_BOX = (18, 82, WIDTH - 19, 426)
INPUT_BOX = (18, 439, WIDTH - 19, 484)
VIEWPORT_WIDTH = VIEWPORT_BOX[2] - VIEWPORT_BOX[0] + 1
VIEWPORT_HEIGHT = VIEWPORT_BOX[3] - VIEWPORT_BOX[1] + 1
CONTENT_TOP = 10
SCROLL_BOTTOM_PADDING = 60
PROFILE_CARD_OFFSET = 115
PROFILE_CARD_VISIBLE_TOP = 6

TURN_STARTS = (2.0, 13.4, 24.8)
INPUT_TYPING_DURATION = 1.55
SEND_DURATION = 0.45
USER_APPEAR_DURATION = 0.35
THINK_DURATION = 1.5
TOOL_DURATION = 0.8
RESPONSE_DURATION = 3.0
FINAL_START = 36.4
FADE_OUT_START = 40.8
AVATAR_FILES = (
    Path("assets/kevin-avatar-wave-1.png"),
    Path("assets/kevin-avatar-wave-2.png"),
)


@dataclass(frozen=True)
class ProfileTurn:
    prompt: str
    thinking: str
    tool: str
    response: str
    accent: tuple[int, int, int]
    height: int
    profile_card: bool = False


TURNS = (
    ProfileTurn(
        prompt="Show me Kevin's developer profile.",
        thinking="Building a concise developer profile",
        tool="Read(profile/kevin.md)",
        response="Here is Kevin's developer profile.",
        accent=TERRACOTTA,
        height=330,
        profile_card=True,
    ),
    ProfileTurn(
        prompt="Tell me about Kevin and what he does.",
        thinking="Connecting his interests with his work",
        tool="Read(profile/about.md)",
        response=(
            "Kevin turns complex ideas and business needs into secure, "
            "scalable, and intuitive web products. He enjoys solving "
            "real-world problems and creating experiences with meaningful value."
        ),
        accent=BLUE,
        height=152,
    ),
    ProfileTurn(
        prompt="What does Kevin bring to a team?",
        thinking="Synthesizing his strengths and direction",
        tool="Analyze(profile/work-style.json)",
        response=(
            "He brings ownership, clarity, thoughtful engineering, and a "
            "growth mindset. He is advancing in architecture, cloud, DevOps, "
            "and applied AI while pursuing high-impact work."
        ),
        accent=GREEN,
        height=152,
    ),
)


def load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """Load a readable monospace font on macOS and GitHub's Ubuntu runner."""
    candidates = (
        (
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
        ),
        (
            "/System/Library/Fonts/Supplemental/Andale Mono.ttf"
            if bold
            else "/System/Library/Fonts/Menlo.ttc"
        ),
        (
            "/Library/Fonts/DejaVuSansMono-Bold.ttf"
            if bold
            else "/Library/Fonts/DejaVuSansMono.ttf"
        ),
    )
    for font_path in candidates:
        try:
            return ImageFont.truetype(font_path, size)
        except OSError:
            continue
    return ImageFont.load_default()


FONT_SMALL = load_font(12)
FONT_BODY = load_font(14)
FONT_BODY_BOLD = load_font(14, bold=True)
FONT_PROMPT = load_font(15, bold=True)
FONT_TITLE = load_font(18, bold=True)


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def ease(value: float) -> float:
    progress = clamp(value)
    return progress * progress * (3 - 2 * progress)


def blend(
    base: tuple[int, int, int],
    accent: tuple[int, int, int],
    amount: float,
) -> tuple[int, int, int]:
    intensity = clamp(amount)
    return tuple(
        round(background + (foreground - background) * intensity)
        for background, foreground in zip(base, accent)
    )


def partial_text(text: str, progress: float) -> str:
    visible_characters = round(len(text) * clamp(progress))
    return text[:visible_characters]


def wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    """Wrap text using measured pixel width rather than character count."""
    if not text:
        return [""]

    words = text.split(" ")
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def draw_spark(
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    frame_index: int,
) -> None:
    """Draw an original animated agent mark without copying a product logo."""
    center_x, center_y = center
    rotation = frame_index / 54 * 2 * pi
    pulse = (1 - cos(frame_index / 18 * 2 * pi)) / 2
    for ray_index in range(8):
        angle = rotation + ray_index * pi / 4
        inner_radius = 5
        outer_radius = 11 + round(pulse * 2)
        draw.line(
            (
                center_x + cos(angle) * inner_radius,
                center_y + sin(angle) * inner_radius,
                center_x + cos(angle) * outer_radius,
                center_y + sin(angle) * outer_radius,
            ),
            fill=blend(TERRACOTTA, TERRACOTTA_BRIGHT, pulse),
            width=2,
        )
    draw.ellipse(
        (center_x - 3, center_y - 3, center_x + 3, center_y + 3),
        fill=TERRACOTTA_BRIGHT,
    )


def turn_sent_at(start: float) -> float:
    return start + INPUT_TYPING_DURATION + SEND_DURATION


def response_starts_at(sent_at: float) -> float:
    return sent_at + USER_APPEAR_DURATION + THINK_DURATION + TOOL_DURATION


def turn_offsets() -> tuple[int, ...]:
    offsets: list[int] = []
    current_offset = 0
    for turn in TURNS:
        offsets.append(current_offset)
        current_offset += turn.height
    return tuple(offsets)


def total_turn_height() -> int:
    return sum(turn.height for turn in TURNS)


def active_turn_count(time_seconds: float) -> int:
    return sum(
        time_seconds >= turn_sent_at(start)
        for start in TURN_STARTS
    )


def draw_header(
    draw: ImageDraw.ImageDraw,
    time_seconds: float,
    frame_index: int,
) -> None:
    glow = (1 - cos(frame_index / 30 * 2 * pi)) / 2
    draw.rounded_rectangle(
        HEADER_BOX,
        radius=12,
        fill=PANEL,
        outline=blend(BORDER, TERRACOTTA, 0.12 + glow * 0.18),
        width=2,
    )
    draw_spark(draw, (40, 42), frame_index)
    draw.text(
        (62, 25),
        "Kevin Profile Agent",
        fill=TEXT,
        font=FONT_TITLE,
    )
    draw.text(
        (62, 48),
        "~/about-me",
        fill=MUTED,
        font=FONT_SMALL,
    )

    completed = active_turn_count(time_seconds)
    draw.text(
        (553, 25),
        f"CONTEXT {completed}/3",
        fill=MUTED,
        font=FONT_SMALL,
    )
    for segment_index in range(3):
        segment_x = 554 + segment_index * 35
        segment_color = (
            GREEN
            if segment_index < completed
            else blend(PANEL, BORDER, 0.9)
        )
        draw.rounded_rectangle(
            (segment_x, 48, segment_x + 26, 52),
            radius=2,
            fill=segment_color,
        )

    status_color = GREEN if completed == 3 else TERRACOTTA
    draw.ellipse((695, 29, 703, 37), fill=status_color)
    draw.text(
        (708, 25),
        "LIVE",
        fill=status_color,
        font=FONT_SMALL,
    )


def scroll_offset(time_seconds: float) -> float:
    """Smoothly move older turns upward as the conversation grows."""
    profile_card_target = (
        CONTENT_TOP
        + PROFILE_CARD_OFFSET
        - PROFILE_CARD_VISIBLE_TOP
    )
    final_turn_target = max(
        0,
        total_turn_height()
        - VIEWPORT_HEIGHT
        + SCROLL_BOTTOM_PADDING,
    )
    turn_targets = (
        0,
        profile_card_target,
        final_turn_target,
    )

    scroll = 0.0
    previous_target = 0.0
    for target, start in zip(turn_targets, TURN_STARTS):
        scroll += (target - previous_target) * ease(
            (time_seconds - start) / 1.15
        )
        previous_target = target

    before_final = turn_targets[-1]
    after_final = max(
        0,
        total_turn_height()
        + 82
        - VIEWPORT_HEIGHT
        + SCROLL_BOTTOM_PADDING,
    )
    scroll += (after_final - before_final) * ease(
        (time_seconds - FINAL_START) / 0.9
    )
    return scroll


def draw_activity_rail(
    draw: ImageDraw.ImageDraw,
    time_seconds: float,
    content_scroll: float,
) -> None:
    rail_x = 21
    offsets = turn_offsets()
    first_y = CONTENT_TOP + 15 - content_scroll
    last_y = (
        CONTENT_TOP
        + offsets[-1]
        + 15
        - content_scroll
    )
    draw.line(
        (rail_x, first_y, rail_x, last_y),
        fill=BORDER,
        width=2,
    )
    for turn, start, offset in zip(TURNS, TURN_STARTS, offsets):
        sent_at = turn_sent_at(start)
        node_y = CONTENT_TOP + offset + 15 - content_scroll
        completed_at = (
            response_starts_at(sent_at)
            + RESPONSE_DURATION
        )
        if time_seconds >= completed_at:
            color = GREEN
        elif time_seconds >= sent_at:
            color = turn.accent
        else:
            color = BORDER
        draw.ellipse(
            (rail_x - 5, node_y - 5, rail_x + 5, node_y + 5),
            fill=PANEL_DEEP,
            outline=color,
            width=2,
        )
        if time_seconds >= sent_at and time_seconds < completed_at:
            pulse = (1 - cos((time_seconds - sent_at) * 5 * pi)) / 2
            radius = 7 + round(pulse * 2)
            draw.ellipse(
                (
                    rail_x - radius,
                    node_y - radius,
                    rail_x + radius,
                    node_y + radius,
                ),
                outline=blend(PANEL_DEEP, color, 0.25),
            )


def draw_tool_row(
    draw: ImageDraw.ImageDraw,
    turn: ProfileTurn,
    elapsed: float,
    y: float,
    frame_index: int,
) -> None:
    thinking_start = USER_APPEAR_DURATION
    tool_start = thinking_start + THINK_DURATION
    tool_end = tool_start + TOOL_DURATION

    if elapsed < thinking_start:
        return
    if elapsed < tool_start:
        draw_spark(draw, (64, round(y + 10)), frame_index)
        dots = "." * (1 + (frame_index // 4) % 3)
        draw.text(
            (84, y - 1),
            f"Thinking{dots}",
            fill=TERRACOTTA_BRIGHT,
            font=FONT_BODY_BOLD,
        )
        draw.text(
            (84, y + 18),
            turn.thinking,
            fill=MUTED,
            font=FONT_SMALL,
        )
        return

    tool_progress = clamp((elapsed - tool_start) / TOOL_DURATION)
    completed = elapsed >= tool_end
    symbol = "+" if completed else ">"
    symbol_color = GREEN if completed else BLUE
    draw.text(
        (55, y + 5),
        f"[{symbol}]",
        fill=symbol_color,
        font=FONT_BODY_BOLD,
    )
    draw.text(
        (86, y + 6),
        turn.tool,
        fill=BLUE,
        font=FONT_SMALL,
    )

    bar_x = 306
    bar_y = round(y + 11)
    draw.rounded_rectangle(
        (bar_x, bar_y, bar_x + 96, bar_y + 5),
        radius=2,
        fill=(34, 40, 48),
    )
    draw.rounded_rectangle(
        (
            bar_x,
            bar_y,
            bar_x + round(96 * tool_progress),
            bar_y + 5,
        ),
        radius=2,
        fill=GREEN if completed else BLUE,
    )
    draw.text(
        (414, y + 6),
        "done" if completed else f"{round(tool_progress * 100):>3}%",
        fill=GREEN if completed else MUTED,
        font=FONT_SMALL,
    )


@lru_cache(maxsize=1)
def load_avatar_frames() -> tuple[Image.Image, ...]:
    """Prepare the existing waving avatar for the compact profile card."""
    frames: list[Image.Image] = []
    for avatar_path in AVATAR_FILES:
        with Image.open(avatar_path) as source:
            avatar = source.convert("RGB")
            for corner in (
                (0, 0),
                (avatar.width - 1, 0),
                (0, avatar.height - 1),
                (avatar.width - 1, avatar.height - 1),
            ):
                ImageDraw.floodfill(
                    avatar,
                    corner,
                    PANEL,
                    thresh=20,
                )
            avatar = avatar.crop((35, 70, 1219, 1254))
            frames.append(
                avatar.resize(
                    (196, 196),
                    Image.Resampling.LANCZOS,
                )
            )
    return tuple(frames)


def animated_avatar(frame_index: int) -> Image.Image:
    frames = load_avatar_frames()
    frames_per_pose = 10
    transition_frames = 4
    pose_index = (frame_index // frames_per_pose) % len(frames)
    next_index = (pose_index + 1) % len(frames)
    frame_in_pose = frame_index % frames_per_pose
    transition_start = frames_per_pose - transition_frames
    transition_progress = clamp(
        (frame_in_pose - transition_start)
        / max(1, transition_frames - 1)
    )
    return Image.blend(
        frames[pose_index],
        frames[next_index],
        ease(transition_progress),
    )


def draw_profile_card(
    surface: Image.Image,
    draw: ImageDraw.ImageDraw,
    y: float,
    reveal: float,
    frame_index: int,
) -> None:
    card_progress = ease((reveal - 0.62) / 0.34)
    if card_progress <= 0:
        return

    card_left = 62
    card_top = round(y)
    card_right = round(
        card_left + (VIEWPORT_WIDTH - 74) * card_progress
    )
    card_bottom = card_top + 204
    draw.rounded_rectangle(
        (card_left, card_top, card_right, card_bottom),
        radius=10,
        fill=PANEL,
        outline=blend(BORDER, TERRACOTTA, 0.48),
        width=2,
    )
    if card_progress < 0.72:
        return

    glow = (1 - cos(frame_index / 28 * 2 * pi)) / 2
    draw.rounded_rectangle(
        (70, card_top + 4, 278, card_top + 200),
        radius=9,
        outline=blend(PANEL, TERRACOTTA, 0.28 + glow * 0.32),
        width=2,
    )
    surface.paste(
        animated_avatar(frame_index),
        (76, card_top + 4),
    )
    draw.text(
        (296, card_top + 22),
        "Kevin Alfredo Martínez",
        fill=TEXT,
        font=FONT_BODY_BOLD,
    )
    draw.text(
        (296, card_top + 58),
        "Full-Stack Developer",
        fill=TERRACOTTA_BRIGHT,
        font=FONT_SMALL,
    )
    draw.text(
        (296, card_top + 90),
        "Guatemala  //  Age 23",
        fill=TERRACOTTA_BRIGHT,
        font=FONT_SMALL,
    )
    draw.text(
        (296, card_top + 128),
        "Secure products  ·  Scalable systems",
        fill=MUTED,
        font=FONT_SMALL,
    )
    draw.text(
        (296, card_top + 158),
        "Meaningful real-world impact",
        fill=MUTED,
        font=FONT_SMALL,
    )


def draw_turn(
    surface: Image.Image,
    draw: ImageDraw.ImageDraw,
    turn: ProfileTurn,
    start: float,
    time_seconds: float,
    y: float,
    frame_index: int,
) -> None:
    sent_at = turn_sent_at(start)
    elapsed = time_seconds - sent_at
    if elapsed < 0:
        return

    message_reveal = ease(elapsed / USER_APPEAR_DURATION)
    message_right = round(
        58 + (VIEWPORT_WIDTH - 86) * message_reveal
    )
    draw.rounded_rectangle(
        (42, y, message_right, y + 34),
        radius=8,
        fill=blend(PANEL_DEEP, PANEL, 0.78),
        outline=blend(BORDER, turn.accent, 0.25),
    )
    if message_reveal < 0.45:
        return
    draw.text(
        (55, y + 8),
        ">",
        fill=turn.accent,
        font=FONT_PROMPT,
    )
    draw.text(
        (75, y + 8),
        turn.prompt,
        fill=TEXT,
        font=FONT_PROMPT,
    )

    draw_tool_row(
        draw,
        turn,
        elapsed,
        y + 44,
        frame_index,
    )

    response_start = USER_APPEAR_DURATION + THINK_DURATION + TOOL_DURATION
    if elapsed < response_start:
        return

    response_progress = (elapsed - response_start) / RESPONSE_DURATION
    visible_response = partial_text(turn.response, response_progress)
    response_lines = wrap_text(
        draw,
        visible_response,
        FONT_BODY,
        VIEWPORT_WIDTH - 122,
    )
    line_height = 19
    response_top = y + 84
    draw_spark(
        draw,
        (57, round(response_top + 8)),
        frame_index,
    )
    draw.line(
        (
            76,
            response_top - 2,
            76,
            response_top + max(18, len(response_lines) * line_height - 4),
        ),
        fill=blend(PANEL_DEEP, turn.accent, 0.75),
        width=2,
    )
    for line_index, line in enumerate(response_lines):
        draw.text(
            (88, response_top + line_index * line_height),
            line,
            fill=TEXT,
            font=FONT_BODY,
        )

    if turn.profile_card:
        draw_profile_card(
            surface,
            draw,
            response_top + 31,
            response_progress,
            frame_index,
        )


def draw_final_status(
    draw: ImageDraw.ImageDraw,
    time_seconds: float,
    y: float,
    frame_index: int,
) -> None:
    if time_seconds < FINAL_START:
        return

    reveal = ease((time_seconds - FINAL_START) / 0.8)
    box_right = round(55 + (VIEWPORT_WIDTH - 86) * reveal)
    draw.rounded_rectangle(
        (42, y, box_right, y + 62),
        radius=10,
        fill=PANEL,
        outline=blend(BORDER, GREEN, 0.45),
        width=2,
    )
    if reveal < 0.55:
        return

    check_pulse = (1 - cos(frame_index / 24 * 2 * pi)) / 2
    draw.ellipse(
        (57, y + 15, 79, y + 37),
        fill=blend(PANEL, GREEN, 0.18 + check_pulse * 0.12),
        outline=GREEN,
        width=2,
    )
    draw.line(
        (63, y + 26, 68, y + 31, 75, y + 21),
        fill=GREEN,
        width=2,
    )
    draw.text(
        (91, y + 10),
        "Conversation complete",
        fill=TEXT,
        font=FONT_BODY_BOLD,
    )
    draw.text(
        (91, y + 34),
        "Kevin's profile is ready",
        fill=GREEN,
        font=FONT_SMALL,
    )


def draw_conversation(
    image: Image.Image,
    time_seconds: float,
    frame_index: int,
) -> None:
    viewport = Image.new(
        "RGB",
        (VIEWPORT_WIDTH, VIEWPORT_HEIGHT),
        PANEL_DEEP,
    )
    draw = ImageDraw.Draw(viewport)
    content_scroll = scroll_offset(time_seconds)

    for grid_y in range(18, VIEWPORT_HEIGHT, 28):
        draw.line(
            (0, grid_y, VIEWPORT_WIDTH, grid_y),
            fill=(20, 25, 31),
        )

    draw_activity_rail(draw, time_seconds, content_scroll)
    for turn, start, offset in zip(
        TURNS,
        TURN_STARTS,
        turn_offsets(),
    ):
        turn_y = (
            CONTENT_TOP
            + offset
            - content_scroll
        )
        draw_turn(
            viewport,
            draw,
            turn,
            start,
            time_seconds,
            turn_y,
            frame_index,
        )

    final_y = (
        CONTENT_TOP
        + total_turn_height()
        - content_scroll
    )
    draw_final_status(
        draw,
        time_seconds,
        final_y,
        frame_index,
    )
    viewport_mask = Image.new(
        "L",
        (VIEWPORT_WIDTH, VIEWPORT_HEIGHT),
        0,
    )
    mask_draw = ImageDraw.Draw(viewport_mask)
    mask_draw.rounded_rectangle(
        (0, 0, VIEWPORT_WIDTH - 1, VIEWPORT_HEIGHT - 1),
        radius=12,
        fill=255,
    )
    image.paste(
        viewport,
        (VIEWPORT_BOX[0], VIEWPORT_BOX[1]),
        viewport_mask,
    )


def draw_input(
    draw: ImageDraw.ImageDraw,
    time_seconds: float,
    frame_index: int,
) -> None:
    active_turn: ProfileTurn | None = None
    active_start = 0.0
    for turn, start in zip(TURNS, TURN_STARTS):
        if start <= time_seconds < turn_sent_at(start):
            active_turn = turn
            active_start = start
            break

    complete = time_seconds >= FINAL_START
    active = active_turn is not None
    border_color = (
        GREEN
        if complete
        else TERRACOTTA
        if active
        else BORDER
    )
    pulse = (1 - cos(frame_index / 32 * 2 * pi)) / 2
    draw.rounded_rectangle(
        INPUT_BOX,
        radius=11,
        fill=PANEL,
        outline=blend(BORDER, border_color, 0.55 + pulse * 0.3),
        width=2,
    )
    draw.text(
        (35, 452),
        ">",
        fill=(
            GREEN
            if complete
            else TERRACOTTA_BRIGHT
            if active
            else MUTED
        ),
        font=FONT_PROMPT,
    )
    send_progress = 0.0
    if active_turn is not None:
        elapsed = time_seconds - active_start
        typing_progress = elapsed / INPUT_TYPING_DURATION
        input_text = partial_text(
            active_turn.prompt,
            typing_progress,
        )
        sending = elapsed >= INPUT_TYPING_DURATION
        if not sending and (frame_index // 5) % 2 == 0:
            input_text += "_"
        send_progress = ease(
            (elapsed - INPUT_TYPING_DURATION) / SEND_DURATION
        )
        color = TEXT
    elif complete:
        input_text = "Session ended"
        color = GREEN
    elif time_seconds < TURN_STARTS[0]:
        input_text = "Ask about Kevin..."
        color = MUTED
    else:
        input_text = "Message sent"
        color = MUTED
    draw.text(
        (56, 452),
        input_text,
        fill=color,
        font=FONT_BODY,
    )

    button_fill = (
        GREEN
        if complete
        else blend(PANEL, TERRACOTTA, 0.35 + send_progress * 0.65)
        if active
        else (34, 40, 48)
    )
    button_y = 446 - round(send_progress * 2)
    draw.rounded_rectangle(
        (681, button_y, 718, button_y + 30),
        radius=9,
        fill=button_fill,
        outline=blend(BORDER, border_color, 0.65),
    )
    arrow_color = TEXT if active or complete else MUTED
    arrow_x = 699
    if complete:
        draw.line(
            (
                arrow_x - 7,
                button_y + 15,
                arrow_x - 2,
                button_y + 20,
                arrow_x + 8,
                button_y + 10,
            ),
            fill=arrow_color,
            width=2,
        )
    else:
        draw.line(
            (
                arrow_x,
                button_y + 21,
                arrow_x,
                button_y + 9,
            ),
            fill=arrow_color,
            width=2,
        )
        draw.line(
            (
                arrow_x - 5,
                button_y + 14,
                arrow_x,
                button_y + 9,
                arrow_x + 5,
                button_y + 14,
            ),
            fill=arrow_color,
            width=2,
        )


def draw_background_activity(
    draw: ImageDraw.ImageDraw,
    frame_index: int,
) -> None:
    for node_index, (node_x, node_y, color) in enumerate(
        (
            (8, 106, TERRACOTTA),
            (742, 155, BLUE),
            (8, 347, PURPLE),
            (742, 394, GREEN),
        )
    ):
        phase = (
            1
            - cos(2 * pi * (frame_index / 66 + node_index * 0.18))
        ) / 2
        radius = 1 + round(phase * 2)
        draw.ellipse(
            (
                node_x - radius,
                node_y - radius,
                node_x + radius,
                node_y + radius,
            ),
            fill=blend(BACKGROUND, color, 0.3 + phase * 0.6),
        )


def draw_frame(frame_index: int) -> Image.Image:
    time_seconds = frame_index / FPS
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)

    draw_background_activity(draw, frame_index)
    draw.rounded_rectangle(
        (4, 4, WIDTH - 5, HEIGHT - 5),
        radius=18,
        fill=BACKGROUND,
        outline=BORDER,
        width=2,
    )
    draw_header(draw, time_seconds, frame_index)
    draw.rounded_rectangle(
        VIEWPORT_BOX,
        radius=12,
        fill=PANEL_DEEP,
        outline=BORDER,
        width=2,
    )
    draw_conversation(image, time_seconds, frame_index)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        VIEWPORT_BOX,
        radius=12,
        outline=BORDER,
        width=2,
    )
    draw_input(draw, time_seconds, frame_index)

    fade = 1.0
    if time_seconds < 0.8:
        fade = ease(time_seconds / 0.8)
    elif time_seconds > FADE_OUT_START:
        fade = ease(
            (DURATION_SECONDS - time_seconds)
            / (DURATION_SECONDS - FADE_OUT_START)
        )
    if fade < 1.0:
        image = Image.blend(
            Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND),
            image,
            fade,
        )
    return image


def resolve_ffmpeg() -> str:
    configured = os.getenv("FFMPEG_BINARY")
    if configured and Path(configured).exists():
        return configured

    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError) as error:
        raise RuntimeError(
            "FFmpeg is required. Install ffmpeg or set FFMPEG_BINARY."
        ) from error


def encode_gif(frames_directory: Path) -> None:
    ffmpeg = resolve_ffmpeg()
    frame_pattern = str(frames_directory / "frame_%04d.png")
    filter_graph = (
        "[0:v]split[palette_input][gif_input];"
        "[palette_input]palettegen=max_colors=128:stats_mode=diff[palette];"
        "[gif_input][palette]paletteuse="
        "dither=bayer:bayer_scale=3:diff_mode=rectangle"
    )
    subprocess.run(
        (
            ffmpeg,
            "-v",
            "error",
            "-y",
            "-framerate",
            str(FPS),
            "-i",
            frame_pattern,
            "-filter_complex",
            filter_graph,
            "-loop",
            "0",
            str(OUTPUT_FILE),
        ),
        check=True,
    )


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="kevin-profile-agent-") as temp_dir:
        frames_directory = Path(temp_dir)
        for frame_index in range(FRAME_COUNT):
            frame = draw_frame(frame_index)
            frame.save(
                frames_directory / f"frame_{frame_index:04d}.png",
                compress_level=5,
            )
        encode_gif(frames_directory)

    print(
        f"Generated {OUTPUT_FILE}: "
        f"{WIDTH}x{HEIGHT}, {FRAME_COUNT} frames, "
        f"{DURATION_SECONDS}s at {FPS} FPS"
    )


if __name__ == "__main__":
    main()
