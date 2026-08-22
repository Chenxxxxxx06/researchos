"""Local, compilation-safe venue starters and policy metadata.

These starters intentionally use only TeX Live core packages. Before final
submission, authors must sync the official class/style from the recorded venue
URL because conference style files change by year.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VenueTemplate:
    template_id: str
    venue: str
    official_url: str
    main_tex: str


def _starter(venue: str, sections: tuple[str, ...], *, anonymous: bool = True) -> str:
    section_text = "\n".join(f"\\section{{{section}}}\n" for section in sections)
    author = "Anonymous Authors" if anonymous else "Author Name"
    return rf"""% ResearchOS offline starter for {venue}.
% Sync the current official style from the venue URL before submission.
\documentclass[10pt]{{article}}
\usepackage[T1]{{fontenc}}
\usepackage{{microtype}}
\usepackage{{amsmath,amssymb,booktabs,graphicx,hyperref}}
\title{{Paper Title}}
\author{{{author}}}
\begin{{document}}
\maketitle
\begin{{abstract}}
State the problem, evidence-backed method, verified results, and limitations.
\end{{abstract}}
{section_text}
\bibliographystyle{{plain}}
\bibliography{{references}}
\end{{document}}
"""


VENUE_TEMPLATES: dict[str, VenueTemplate] = {
    "neurips": VenueTemplate(
        "neurips",
        "NeurIPS",
        "https://neurips.cc/Conferences/2025/PaperInformation/StyleFiles",
        _starter(
            "NeurIPS",
            (
                "Introduction",
                "Related Work",
                "Method",
                "Experiments",
                "Ablations",
                "Limitations",
                "Conclusion",
            ),
        ),
    ),
    "icml": VenueTemplate(
        "icml",
        "ICML",
        "https://icml.cc/Conferences/2025/AuthorInstructions",
        _starter(
            "ICML",
            (
                "Introduction",
                "Related Work",
                "Method",
                "Theoretical Analysis",
                "Experiments",
                "Ablations",
                "Conclusion",
            ),
        ),
    ),
    "iclr": VenueTemplate(
        "iclr",
        "ICLR",
        "https://iclr.cc/Conferences/2026/AuthorGuide",
        _starter(
            "ICLR",
            (
                "Introduction",
                "Related Work",
                "Method",
                "Experiments",
                "Analysis and Ablations",
                "Reproducibility",
                "Conclusion",
            ),
        ),
    ),
    "cvpr": VenueTemplate(
        "cvpr",
        "CVPR",
        "https://cvpr.thecvf.com/Conferences/2026/AuthorGuidelines",
        _starter(
            "CVPR",
            (
                "Introduction",
                "Related Work",
                "Method",
                "Experiments",
                "Ablation Studies",
                "Qualitative Analysis",
                "Limitations",
                "Conclusion",
            ),
        ),
    ),
    "acl": VenueTemplate(
        "acl",
        "ACL",
        "https://acl-org.github.io/ACLPUB/formatting.html",
        _starter(
            "ACL",
            (
                "Introduction",
                "Related Work",
                "Method",
                "Experimental Setup",
                "Results",
                "Analysis",
                "Limitations",
                "Ethics Statement",
                "Conclusion",
            ),
        ),
    ),
    "aaai": VenueTemplate(
        "aaai",
        "AAAI",
        "https://aaai.org/authorkit26/",
        _starter(
            "AAAI",
            (
                "Introduction",
                "Related Work",
                "Method",
                "Experiments",
                "Results and Discussion",
                "Limitations",
                "Conclusion",
            ),
        ),
    ),
}
