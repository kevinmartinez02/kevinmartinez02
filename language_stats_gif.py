from collections import Counter
from math import cos, pi, sin
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import requests

GITHUB_USER = "kevinmartinez02"
OUTPUT_FILE = Path("language-stats.gif")

WIDTH = 900
HEIGHT = 360
FPS = 15
DURATION_SECONDS = 8

BACKGROUND = (13, 17, 23)
PANEL = (10, 14, 20)
BORDER = (48, 54, 61)
TEXT = (240, 246, 252)
MUTED = (139, 148, 158)
BLUE = (88, 166, 255)
GREEN = (63, 185, 80)
PURPLE = (210, 168, 255)

LANGUAGE_COLORS = {
    "TypeScript": (49, 120, 198),
    "JavaScript": (241, 224, 90),
    "Python": (53, 114, 165),
    "PHP": (119, 123, 180),
    "Blade": (241, 82, 63),
    "HTML": (227, 76, 38),
    "CSS": (86, 61, 124),
    "Dockerfile": (56, 151, 240),
    "Hack": (135, 206, 235),
}
FALLBACK_COLORS = (
    BLUE,
    (227, 179, 65),
    (248, 81, 73),
    PURPLE,
)
FALLBACK_LANGUAGES = [
    ("PHP", 34.4),
    ("Blade", 27.8),
    ("TypeScript", 23.5),
    ("JavaScript", 6.6),
]


def load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """Load a monospace font on macOS and GitHub's Ubuntu runner."""
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
        "/Library/Fonts/DejaVuSansMono.ttf",
    )
    for font_path in candidates:
        try:
            return ImageFont.truetype(font_path, size)
        except OSError:
            continue
    return ImageFont.load_default()


FONT_SMALL = load_font(12)
FONT_LABEL = load_font(17, bold=True)
FONT_TITLE = load_font(22, bold=True)


def fetch_language_stats() -> tuple[list[tuple[str, float]], int]:
    """Calculate public language percentages from GitHub's byte counts."""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "kevinmartinez02-language-pulse",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        repos_response = requests.get(
            f"https://api.github.com/users/{GITHUB_USER}/repos",
            headers=headers,
            params={"per_page": 100, "type": "owner"},
            timeout=20,
        )
        repos_response.raise_for_status()
        repos = repos_response.json()

        language_bytes: Counter[str] = Counter()
        for repo in repos:
            languages_url = repo.get("languages_url")
            if not languages_url:
                continue
            response = requests.get(
                languages_url,
                headers=headers,
                timeout=20,
            )
            response.raise_for_status()
            language_bytes.update(response.json())

        total_bytes = sum(language_bytes.values())
        if not total_bytes:
            return FALLBACK_LANGUAGES, len(repos)

        top_languages = [
            (language, round(byte_count / total_bytes * 100, 1))
            for language, byte_count in language_bytes.most_common(4)
        ]
        return top_languages, len(repos)
    except (requests.RequestException, ValueError, KeyError):
        return FALLBACK_LANGUAGES, 12


def blend(
    base: tuple[int, int, int],
    accent: tuple[int, int, int],
    intensity: float,
) -> tuple[int, int, int]:
    return tuple(
        int(background + (foreground - background) * intensity)
        for background, foreground in zip(base, accent)
    )


def language_color(language: str, index: int) -> tuple[int, int, int]:
    return LANGUAGE_COLORS.get(
        language,
        FALLBACK_COLORS[index % len(FALLBACK_COLORS)],
    )


def point_on_path(
    points: tuple[tuple[int, int], ...],
    progress: float,
) -> tuple[int, int]:
    segment_lengths = [
        ((end_x - start_x) ** 2 + (end_y - start_y) ** 2) ** 0.5
        for (start_x, start_y), (end_x, end_y) in zip(points, points[1:])
    ]
    total_length = sum(segment_lengths)
    distance = (progress % 1.0) * total_length

    for index, segment_length in enumerate(segment_lengths):
        if distance <= segment_length:
            start_x, start_y = points[index]
            end_x, end_y = points[index + 1]
            ratio = distance / max(1, segment_length)
            return (
                int(start_x + (end_x - start_x) * ratio),
                int(start_y + (end_y - start_y) * ratio),
            )
        distance -= segment_length
    return points[-1]


def draw_glow(
    draw: ImageDraw.ImageDraw,
    position: tuple[int, int],
    color: tuple[int, int, int],
) -> None:
    x, y = position
    for radius, intensity in ((10, 0.09), (6, 0.23), (3, 1.0)):
        draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius),
            fill=blend(BACKGROUND, color, intensity),
        )


def reveal_for_frame(
    frame_index: int,
    frame_count: int,
    lane_index: int = 0,
) -> float:
    """Load each percentage gradually, with a visible lane-by-lane delay."""
    phase = frame_index / max(1, frame_count - 1)
    start = 0.05 + lane_index * 0.035
    finish = 0.50 + lane_index * 0.035
    if phase < start:
        return 0.0
    if phase < finish:
        progress = (phase - start) / (finish - start)
        return (1 - cos(pi * progress)) / 2
    if phase > 0.94:
        progress = (1 - phase) / 0.06
        return max(0.0, (1 - cos(pi * progress)) / 2)
    return 1.0


def draw_inbound_network(
    draw: ImageDraw.ImageDraw,
    frame_index: int,
) -> None:
    """Feed the core with an unlabeled circuit network from several sides."""
    input_streams = (
        (
            ((24, 88), (62, 88), (62, 142), (107, 142)),
            BLUE,
            0.00,
        ),
        (
            ((24, 128), (75, 128), (75, 166), (107, 166)),
            PURPLE,
            0.13,
        ),
        (
            ((24, 196), (68, 196), (68, 202), (107, 202)),
            GREEN,
            0.26,
        ),
        (
            ((24, 250), (72, 250), (72, 258), (107, 258)),
            (227, 179, 65),
            0.39,
        ),
        (
            ((24, 312), (82, 312), (82, 286), (107, 286)),
            PURPLE,
            0.52,
        ),
        (
            ((128, 74), (128, 104), (146, 104), (146, 127)),
            BLUE,
            0.65,
        ),
        (
            ((191, 74), (191, 127)),
            GREEN,
            0.78,
        ),
        (
            ((270, 74), (270, 102), (250, 102), (250, 127)),
            PURPLE,
            0.91,
        ),
        (
            ((143, 335), (143, 313)),
            GREEN,
            1.04,
        ),
        (
            ((204, 335), (204, 313)),
            BLUE,
            1.17,
        ),
        (
            ((273, 335), (273, 319), (260, 319), (260, 313)),
            (227, 179, 65),
            1.30,
        ),
    )

    for stream_index, (path, color, offset) in enumerate(input_streams):
        draw.line(
            path,
            fill=blend(BACKGROUND, color, 0.48),
            width=2,
            joint="curve",
        )
        source_x, source_y = path[0]
        draw.ellipse(
            (
                source_x - 4,
                source_y - 4,
                source_x + 4,
                source_y + 4,
            ),
            fill=PANEL,
            outline=color,
            width=2,
        )
        for path_x, path_y in path[1:-1]:
            draw.rectangle(
                (path_x - 2, path_y - 2, path_x + 2, path_y + 2),
                fill=color,
            )

        stream_phase = frame_index / (20 + stream_index % 4 * 3) + offset
        for pulse_offset, intensity in ((0.0, 1.0), (-0.43, 0.62)):
            pulse_x, pulse_y = point_on_path(
                path,
                stream_phase + pulse_offset,
            )
            for radius, glow_intensity in ((6, 0.10), (3, 0.42), (1, 1.0)):
                draw.ellipse(
                    (
                        pulse_x - radius,
                        pulse_y - radius,
                        pulse_x + radius,
                        pulse_y + radius,
                    ),
                    fill=blend(
                        BACKGROUND,
                        color,
                        glow_intensity * intensity,
                    ),
                )


def draw_core_activity(
    draw: ImageDraw.ImageDraw,
    frame_index: int,
) -> None:
    """Render a layered processor with routing, registers, and live signals."""
    inner_background = (13, 24, 34)
    center_x, center_y = 200, 211

    # Animated scan and technical corner brackets.
    scan_y = 165 + round((frame_index % 54) / 53 * 110)
    draw.line(
        (145, scan_y, 255, scan_y),
        fill=blend(inner_background, BLUE, 0.28),
        width=1,
    )
    for x_direction, y_direction in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
        corner_x = center_x + x_direction * 52
        corner_y = center_y + y_direction * 50
        draw.line(
            (
                corner_x,
                corner_y,
                corner_x - x_direction * 13,
                corner_y,
            ),
            fill=blend(inner_background, BLUE, 0.78),
            width=2,
        )
        draw.line(
            (
                corner_x,
                corner_y,
                corner_x,
                corner_y - y_direction * 13,
            ),
            fill=blend(inner_background, BLUE, 0.78),
            width=2,
        )

    # Six processing registers breathe independently.
    for register_index in range(6):
        register_phase = (
            1
            - cos(
                2
                * pi
                * (frame_index / 42 + register_index * 0.14)
            )
        ) / 2
        register_x = 157 + register_index * 17
        draw.rounded_rectangle(
            (register_x, 168, register_x + 10, 172),
            radius=2,
            fill=blend(
                inner_background,
                GREEN if register_index % 2 else BLUE,
                0.22 + register_phase * 0.72,
            ),
        )

    colors = (BLUE, GREEN, PURPLE, (227, 179, 65))
    for node_index, color in enumerate(colors):
        angle = (
            2 * pi * frame_index / 78
            + node_index * pi / 2
        )
        node_x = round(center_x + cos(angle) * 47)
        node_y = round(center_y + sin(angle) * 38)
        draw.line(
            (center_x, center_y, node_x, node_y),
            fill=blend(inner_background, color, 0.28),
            width=1,
        )
        for radius, intensity in ((6, 0.16), (3, 1.0)):
            draw.ellipse(
                (
                    node_x - radius,
                    node_y - radius,
                    node_x + radius,
                    node_y + radius,
                ),
                fill=blend(inner_background, color, intensity),
            )

    rotation = frame_index * 5 % 360
    ring_box = (
        center_x - 39,
        center_y - 39,
        center_x + 39,
        center_y + 39,
    )
    for arc_index, color in enumerate(colors):
        arc_start = rotation + arc_index * 90
        draw.arc(
            ring_box,
            start=arc_start,
            end=arc_start + 48,
            fill=blend(inner_background, color, 0.88),
            width=2,
        )

    energy = (1 - cos(2 * pi * frame_index / 36)) / 2
    core_color = blend(inner_background, BLUE, 0.55 + energy * 0.45)
    processor_shape = (
        (center_x, center_y - 25),
        (center_x + 23, center_y - 13),
        (center_x + 23, center_y + 13),
        (center_x, center_y + 25),
        (center_x - 23, center_y + 13),
        (center_x - 23, center_y - 13),
    )
    draw.polygon(
        processor_shape,
        fill=inner_background,
        outline=core_color,
    )
    draw.line(
        processor_shape + (processor_shape[0],),
        fill=core_color,
        width=2,
        joint="curve",
    )

    core_text = "KM"
    core_text_box = draw.textbbox((0, 0), core_text, font=FONT_LABEL)
    core_text_width = core_text_box[2] - core_text_box[0]
    core_text_height = core_text_box[3] - core_text_box[1]
    draw.text(
        (
            center_x - core_text_width / 2,
            center_y - core_text_height / 2 - 2,
        ),
        core_text,
        fill=TEXT,
        font=FONT_LABEL,
    )

    internal_routes = (
        ((144, 211), (176, 211)),
        ((256, 211), (224, 211)),
        ((200, 161), (200, 186)),
        ((200, 278), (200, 236)),
    )
    for route_index, route in enumerate(internal_routes):
        route_color = colors[route_index]
        draw.line(
            route,
            fill=blend(inner_background, route_color, 0.35),
            width=2,
        )
        packet_x, packet_y = point_on_path(
            route,
            frame_index / 18 + route_index * 0.24,
        )
        draw.ellipse(
            (
                packet_x - 3,
                packet_y - 3,
                packet_x + 3,
                packet_y + 3,
            ),
            fill=blend(inner_background, route_color, 0.72 + energy * 0.28),
        )

    heartbeat_y = 264
    heartbeat = (
        (158, heartbeat_y),
        (176, heartbeat_y),
        (182, heartbeat_y - round(energy * 8)),
        (189, heartbeat_y + round(energy * 6)),
        (196, heartbeat_y),
        (242, heartbeat_y),
    )
    draw.line(
        heartbeat,
        fill=blend(inner_background, GREEN, 0.55 + energy * 0.4),
        width=2,
        joint="curve",
    )


def draw_frame(
    language_stats: list[tuple[str, float]],
    repo_count: int,
    frame_index: int,
    frame_count: int,
) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        (5, 5, WIDTH - 6, HEIGHT - 6),
        radius=18,
        fill=BACKGROUND,
        outline=BORDER,
        width=2,
    )
    draw.rounded_rectangle(
        (18, 15, WIDTH - 19, 62),
        radius=12,
        fill=PANEL,
        outline=BORDER,
    )
    for x, color in (
        (38, (248, 81, 73)),
        (58, (227, 179, 65)),
        (78, GREEN),
    ):
        draw.ellipse((x - 5, 32, x + 5, 42), fill=color)

    draw.text(
        (105, 25),
        "PULSE CIRCUIT // TOP LANGUAGES",
        fill=PURPLE,
        font=FONT_TITLE,
    )
    draw.text(
        (620, 31),
        f"LIVE API  ::  {repo_count} PUBLIC REPOS",
        fill=MUTED,
        font=FONT_SMALL,
    )

    for grid_x in range(28, WIDTH - 28, 32):
        for grid_y in range(82, HEIGHT - 24, 32):
            draw.point((grid_x, grid_y), fill=(27, 33, 40))

    ambient_nodes = (
        (330, 83, BLUE, 0.00),
        (412, 318, GREEN, 0.23),
        (487, 112, PURPLE, 0.47),
        (875, 188, (227, 179, 65), 0.71),
    )
    for node_x, node_y, color, offset in ambient_nodes:
        pulse = (
            1
            - cos(2 * pi * (frame_index / 60 + offset))
        ) / 2
        radius = 1 + round(pulse * 2)
        draw.ellipse(
            (
                node_x - radius,
                node_y - radius,
                node_x + radius,
                node_y + radius,
            ),
            fill=blend(BACKGROUND, color, 0.25 + pulse * 0.55),
        )

    draw_inbound_network(draw, frame_index)

    glow_phase = (1 - cos(2 * pi * frame_index / 30)) / 2
    draw.rounded_rectangle(
        (93, 113, 307, 327),
        radius=22,
        outline=blend(BACKGROUND, BLUE, 0.13 + glow_phase * 0.16),
        width=3,
    )
    draw.rounded_rectangle(
        (107, 127, 293, 313),
        radius=18,
        fill=PANEL,
        outline=BLUE,
        width=3,
    )
    draw.rounded_rectangle(
        (139, 159, 261, 281),
        radius=14,
        fill=(13, 24, 34),
        outline=blend(BACKGROUND, BLUE, 0.65),
        width=2,
    )
    draw_core_activity(draw, frame_index)

    for pin_y in range(142, 300, 18):
        draw.line((95, pin_y, 107, pin_y), fill=BLUE, width=2)
        draw.line((293, pin_y, 305, pin_y), fill=BLUE, width=2)
    for pin_x in range(125, 285, 20):
        draw.line((pin_x, 115, pin_x, 127), fill=BLUE, width=2)
        draw.line((pin_x, 313, pin_x, 325), fill=BLUE, width=2)

    centers = (92, 160, 228, 296)
    anchors = (155, 190, 225, 260)
    elbows = (350, 390, 430, 470)
    lane_reveals = [
        reveal_for_frame(frame_index, frame_count, lane_index)
        for lane_index in range(4)
    ]
    sync_progress = sum(lane_reveals) / len(lane_reveals)

    for index, ((language, percentage), center_y) in enumerate(
        zip(language_stats[:4], centers)
    ):
        color = language_color(language, index)
        path = (
            (305, anchors[index]),
            (elbows[index], anchors[index]),
            (elbows[index], center_y),
            (520, center_y),
        )
        draw.line(
            path,
            fill=blend(BACKGROUND, color, 0.58),
            width=3,
            joint="curve",
        )
        for path_x, path_y in path[1:-1]:
            draw.rectangle(
                (path_x - 3, path_y - 3, path_x + 3, path_y + 3),
                fill=color,
            )

        card = (520, center_y - 26, 864, center_y + 26)
        draw.rounded_rectangle(
            card,
            radius=9,
            fill=PANEL,
            outline=blend(BACKGROUND, color, 0.92),
            width=2,
        )
        draw.rectangle(
            (528, center_y - 18, 534, center_y + 18),
            fill=color,
        )

        visible_percentage = percentage * lane_reveals[index]
        draw.text(
            (550, center_y - 18),
            language[:15],
            fill=color,
            font=FONT_LABEL,
        )
        percentage_text = f"{visible_percentage:4.1f}%"
        percentage_box = draw.textbbox(
            (0, 0),
            percentage_text,
            font=FONT_LABEL,
        )
        draw.text(
            (845 - (percentage_box[2] - percentage_box[0]), center_y - 18),
            percentage_text,
            fill=TEXT,
            font=FONT_LABEL,
        )

        meter_y = center_y + 12
        for segment in range(16):
            segment_x = 550 + segment * 17
            segment_start = segment / 16 * 100
            segment_end = (segment + 1) / 16 * 100
            segment_progress = min(
                1.0,
                max(
                    0.0,
                    (visible_percentage - segment_start)
                    / (segment_end - segment_start),
                ),
            )
            segment_color = blend(
                (33, 38, 45),
                color,
                segment_progress,
            )
            draw.rounded_rectangle(
                (segment_x, meter_y, segment_x + 11, meter_y + 5),
                radius=2,
                fill=segment_color,
            )

        phase = frame_index / 21 + index * 0.17
        draw_glow(draw, point_on_path(path, phase), color)
        draw_glow(
            draw,
            point_on_path(path, phase - 0.34),
            blend(BACKGROUND, color, 0.74),
        )

    draw.text(
        (330, HEIGHT - 22),
        f"SYNC {round(sync_progress * 100):>3}%  //  PUBLIC LANGUAGE DATA",
        fill=GREEN,
        font=FONT_SMALL,
    )
    draw.text(
        (685, HEIGHT - 22),
        "AUTO-UPDATED DAILY",
        fill=MUTED,
        font=FONT_SMALL,
    )
    return image


def main() -> None:
    language_stats, repo_count = fetch_language_stats()
    frame_count = FPS * DURATION_SECONDS
    frames = [
        draw_frame(language_stats, repo_count, frame_index, frame_count)
        for frame_index in range(frame_count)
    ]
    frames[0].save(
        OUTPUT_FILE,
        save_all=True,
        append_images=frames[1:],
        duration=round(1000 / FPS),
        loop=0,
        optimize=True,
        disposal=2,
    )
    summary = ", ".join(
        f"{language} {percentage:.1f}%"
        for language, percentage in language_stats
    )
    print(f"Generated {OUTPUT_FILE}: {summary}")


if __name__ == "__main__":
    main()
