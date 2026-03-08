from __future__ import annotations

MASTER_PROMPT_TEMPLATE = """Generate a monochrome icon in the same style as the provided reference icon set.

Style requirements:
- solid black fill only
- flat 2D pictogram
- bold geometric silhouette
- modern minimalist corporate/tech icon style
- sharp clean edges
- simple closed shapes
- large negative space
- minimal internal cutouts
- thick connectors and wide gaps
- visually consistent weight
- no gradients
- no shadows
- no outlines
- no texture
- no perspective

Vector-friendly constraints:
- the icon must read as one cohesive symbol
- avoid nested tiny objects
- avoid micro-details
- avoid tiny holes
- avoid thin gaps
- avoid decorative texture
- avoid icon collage compositions
- keep the icon simple enough for clean SVG conversion
- transparent background

Avoid:
- nested tiny objects
- complex inner details
- multiple miniature symbols inside one icon
- very thin circuit traces
- smoke made of small circles
- intricate arrow loops
- tiny wheels
- tiny stars
- tiny screws
- ornamental detail
- photorealism
- sketch style
- soft edges

Requested icon:
{semantic_prompt}
"""

SYSTEM_STYLE_FRAGMENT = (
    "You are generating icons intended for clean SVG conversion. "
    "Prioritize simple bold silhouettes over semantic detail. "
    "Use one dominant metaphor per icon. "
    "Avoid icon collages, micro-details, tiny holes, thin lines, texture, perspective, and ornamental elements. "
    "Every icon must remain clear after thresholding and vector tracing."
)


_SIMPLIFY_MAP = {
    "defense equipment manufacturer": (
        "a bold factory silhouette with one integrated military vehicle cue, "
        "single cohesive pictogram, no tiny wheels, no smoke details"
    ),
    "defence tech startup": (
        "a large simple rocket rising from a symbolic circuit-board base with only 2-3 thick traces, "
        "no thin electronic details"
    ),
    "dual-use technology": (
        "two bold interlocking halves representing civilian and defense use, "
        "one cohesive circular pictogram with minimal internal symbols"
    ),
}


def simplify_semantic_request(label: str) -> str:
    key = label.strip().lower()
    if key in _SIMPLIFY_MAP:
        return _SIMPLIFY_MAP[key]

    words = [w for w in key.replace("-", " ").split() if w]
    trimmed = " ".join(words[:8])
    return (
        f"one dominant integrated symbol for '{trimmed}', with 0-1 supporting cue, "
        "bold silhouette, up to 3 large cutouts, no collage"
    )


def build_prompt(label: str) -> str:
    semantic_prompt = simplify_semantic_request(label)
    return MASTER_PROMPT_TEMPLATE.format(semantic_prompt=semantic_prompt).strip()
