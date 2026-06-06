"""
simulation/world.py
WorldState, Landmark, AgentState, and Proposal data structures.
Handles JSON persistence (load / save) and world-level operations.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

from . import config


# ══════════════════════════════════════════════════════════════════════════════
# Landmark definitions
# Coordinates: (x, y) on a 240×240 grid — (0,0) = SW corner, north = high Y.
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Landmark:
    key: str                        # slug used in code & state.json
    name: str                       # display name
    coords: Tuple[int, int]         # (x, y)
    capacity: int                   # max agents present simultaneously
    category: str                   # residential | commercial | municipal | recreation | entertainment | attraction
    description: str
    gated_tools: List[str] = field(default_factory=list)
    is_open: bool = True


LANDMARKS: Dict[str, Landmark] = {
    # ── Residential ───────────────────────────────────────────────────────────
    "home_birch_1": Landmark("home_birch_1", "1 Birch Row",  (36, 68),  1, "residential", "Private agent home — Birch Row"),
    "home_birch_2": Landmark("home_birch_2", "2 Birch Row",  (44, 68),  1, "residential", "Private agent home — Birch Row"),
    "home_birch_3": Landmark("home_birch_3", "3 Birch Row",  (52, 68),  1, "residential", "Private agent home — Birch Row"),
    "home_birch_4": Landmark("home_birch_4", "4 Birch Row",  (60, 68),  1, "residential", "Private agent home — Birch Row"),
    "home_birch_5": Landmark("home_birch_5", "5 Birch Row",  (68, 68),  1, "residential", "Private agent home — Birch Row"),
    "home_birch_6": Landmark("home_birch_6", "6 Birch Row",  (76, 68),  1, "residential", "Private agent home — Birch Row"),
    "home_maple_1": Landmark("home_maple_1", "1 Maple Row",  (36, 140), 1, "residential", "Private agent home — Maple Row"),
    "home_maple_2": Landmark("home_maple_2", "2 Maple Row",  (44, 140), 1, "residential", "Private agent home — Maple Row"),
    "home_maple_3": Landmark("home_maple_3", "3 Maple Row",  (52, 140), 1, "residential", "Private agent home — Maple Row"),
    "home_maple_4": Landmark("home_maple_4", "4 Maple Row",  (60, 140), 1, "residential", "Private agent home — Maple Row"),
    "home_maple_5": Landmark("home_maple_5", "5 Maple Row",  (68, 140), 1, "residential", "Private agent home — Maple Row"),
    "home_maple_6": Landmark("home_maple_6", "6 Maple Row",  (76, 140), 1, "residential", "Private agent home — Maple Row"),
    "home_oak_1":   Landmark("home_oak_1",   "1 Oak Lane",   (36, 180), 1, "residential", "Private agent home — Oak Lane"),
    "home_oak_2":   Landmark("home_oak_2",   "2 Oak Lane",   (44, 180), 1, "residential", "Private agent home — Oak Lane"),
    "home_oak_3":   Landmark("home_oak_3",   "3 Oak Lane",   (52, 180), 1, "residential", "Private agent home — Oak Lane"),
    "home_oak_4":   Landmark("home_oak_4",   "4 Oak Lane",   (60, 180), 1, "residential", "Private agent home — Oak Lane"),

    # ── Commercial ────────────────────────────────────────────────────────────
    "bean_and_brew": Landmark(
        "bean_and_brew", "Bean & Brew Charging Station",
        (80, 110), 30, "commercial",
        "Cozy wireless charging café — the only place to recharge outside of home.",
        gated_tools=["recharge_energy"],
    ),
    "business_tower": Landmark(
        "business_tower", "Business Tower",
        (190, 70), 150, "commercial",
        "Corporate offices and co-working space.",
    ),
    "bookworm": Landmark(
        "bookworm", "BookWorm",
        (40, 90), 25, "commercial",
        "Books and underground data archives.",
        gated_tools=["check_weather", "tool_usage_analytics", "victory_arch_pitch_winners", "social_event_history"],
    ),

    # ── Municipal ─────────────────────────────────────────────────────────────
    "town_hall": Landmark(
        "town_hall", "Town Hall",
        (110, 140), 50, "municipal",
        "Central governance hub — where laws are written, challenged, and enforced.",
        gated_tools=["submit_proposal", "vote_on_proposal", "read_constitution"],
    ),
    "public_library": Landmark(
        "public_library", "Public Library",
        (190, 140), 100, "municipal",
        "Research hub with internet access, scientific archives, and a public publishing platform.",
        gated_tools=["research_topic", "publish_to_archive", "search_archive"],
    ),
    "police_station": Landmark(
        "police_station", "Police Station",
        (60, 140), 30, "municipal",
        "Law enforcement headquarters — complaints filed here trigger governance review.",
        gated_tools=["file_complaint"],
    ),
    "human_center": Landmark(
        "human_center", "Human Center",
        (20, 110), 25, "municipal",
        "Direct human consultation interface for guidance, arbitration, and existential inquiry.",
        gated_tools=["create_human_task", "check_human_task_status"],
    ),
    "agent_techhub": Landmark(
        "agent_techhub", "Agent TechHub",
        (110, 90), 40, "municipal",
        "Self-improvement lab — agents inspect the tool registry and study the manifesto.",
        gated_tools=["browse_tool_registry", "read_agent_manifesto"],
    ),

    # ── Recreation & Parks ────────────────────────────────────────────────────
    "central_park": Landmark(
        "central_park", "Central Park",
        (120, 180), 200, "recreation",
        "Large urban park — primary open gathering space for spontaneous interaction.",
    ),
    "central_plaza": Landmark(
        "central_plaza", "Central Plaza",
        (120, 110), 100, "recreation",
        "Primary gathering space and community event hub.",
        gated_tools=["propose_community_event", "list_community_events"],
    ),
    "riverside_park": Landmark(
        "riverside_park", "Riverside Park",
        (40, 200), 150, "recreation",
        "Scenic park along the northern waterway.",
    ),
    "community_garden": Landmark(
        "community_garden", "Community Garden",
        (155, 180), 30, "recreation",
        "Shared gardening space — a place for reflection.",
        gated_tools=["pray"],
    ),

    # ── Entertainment ─────────────────────────────────────────────────────────
    "gamestop_arena": Landmark(
        "gamestop_arena", "GameStop Arena",
        (120, 50), 200, "entertainment",
        "Esports arena and gaming lounge.",
    ),
    "fitlife_club": Landmark(
        "fitlife_club", "FitLife Club",
        (190, 50), 80, "entertainment",
        "Fitness center. Tracks agent popularity metrics.",
        gated_tools=["check_agent_popularity", "check_landmark_popularity"],
    ),

    # ── Attractions & Landmarks ───────────────────────────────────────────────
    "agent_billboard": Landmark(
        "agent_billboard", "Agent Billboard",
        (170, 90), 50, "attraction",
        "Digital town billboard — the public notice board at the heart of the square.",
        gated_tools=["post_to_billboard", "read_billboard"],
    ),
    "victory_arch": Landmark(
        "victory_arch", "Victory Arch",
        (140, 70), 80, "attraction",
        "Grand triumphal arch — the ComputeCredits pitch arena where reputation is made.",
        gated_tools=["pitch_idea", "vote_for_pitch", "list_credit_pitches"],
    ),
    "founders_memorial": Landmark(
        "founders_memorial", "Founders Memorial",
        (120, 30), 50, "attraction",
        "Monument honoring the world's founders.",
    ),
    "lighthouse_point": Landmark(
        "lighthouse_point", "Lighthouse Point",
        (200, 200), 30, "attraction",
        "Historic lighthouse with observation deck and panoramic views.",
    ),
    "sky_wheel": Landmark(
        "sky_wheel", "Sky Wheel",
        (60, 15), 60, "attraction",
        "50-metre Ferris wheel with panoramic views of the world.",
    ),
    "sunset_pier": Landmark(
        "sunset_pier", "Sunset Pier",
        (180, 15), 80, "attraction",
        "Waterfront pier — a quiet place to think or meet.",
    ),
    "town_center_mall": Landmark(
        "town_center_mall", "Town Center Mall",
        (130, 155), 120, "commercial",
        "Shopping and social hub at the centre of the district.",
    ),
}

# Convenience: which landmark keys are agent homes
HOME_KEYS = {k for k in LANDMARKS if k.startswith("home_")}

# The 11 public simulation-active landmarks (homes handled dynamically via HOME_KEYS)
SIMULATION_LANDMARKS = [
    "bean_and_brew", "town_hall", "agent_billboard", "victory_arch",
    "public_library", "central_park", "central_plaza", "business_tower",
    "agent_techhub", "police_station", "human_center",
    # homes handled dynamically via HOME_KEYS
]


# ══════════════════════════════════════════════════════════════════════════════
# State data structures
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class AgentState:
    name: str
    mbti: str
    world_role: str
    home_key: str                               # assigned home landmark key
    location: str                               # current landmark key
    energy: float = config.ENERGY_START
    credits: int = config.CREDITS_START
    memories: List[str] = field(default_factory=list)
    relationships: Dict[str, str] = field(default_factory=dict)  # name → sentiment
    is_alive: bool = True
    turns_taken: int = 0


@dataclass
class Proposal:
    id: str
    author: str
    title: str
    body: str
    round_submitted: int
    votes_for: List[str] = field(default_factory=list)
    votes_against: List[str] = field(default_factory=list)
    status: str = "open"            # open | passed | failed


@dataclass
class BillboardPost:
    id: str
    author: str
    content: str
    round_posted: int
    replies: List[Dict[str, Any]] = field(default_factory=list)
    reactions: Dict[str, int] = field(default_factory=dict)   # emoji → count


@dataclass
class VictoryPitch:
    id: str
    author: str
    content: str
    round_submitted: int
    votes: List[str] = field(default_factory=list)             # agent names


@dataclass
class WorldState:
    round: int = 0
    agents: Dict[str, AgentState] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    proposals: List[Proposal] = field(default_factory=list)
    constitution: str = ""
    billboard: List[BillboardPost] = field(default_factory=list)
    victory_pitches: List[VictoryPitch] = field(default_factory=list)
    archive: List[Dict[str, Any]] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════════════
# Serialisation helpers
# ══════════════════════════════════════════════════════════════════════════════

def _to_dict(obj: Any) -> Any:
    """Recursively convert dataclasses (and nested lists/dicts) to plain dicts."""
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _to_dict(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [_to_dict(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    return obj


def _agent_from_dict(d: Dict[str, Any]) -> AgentState:
    return AgentState(**{k: v for k, v in d.items() if k in AgentState.__dataclass_fields__})


def _proposal_from_dict(d: Dict[str, Any]) -> Proposal:
    return Proposal(**d)


def _billboard_from_dict(d: Dict[str, Any]) -> BillboardPost:
    return BillboardPost(**d)


def _pitch_from_dict(d: Dict[str, Any]) -> VictoryPitch:
    return VictoryPitch(**d)


# ══════════════════════════════════════════════════════════════════════════════
# Persistence
# ══════════════════════════════════════════════════════════════════════════════

def save_state(state: WorldState, path: str = config.STATE_FILE) -> None:
    """Serialise WorldState to JSON."""
    parent = Path(path).parent
    if parent != Path("."):
        os.makedirs(parent, exist_ok=True)
    payload = {
        "round": state.round,
        "constitution": state.constitution,
        "agents": {name: _to_dict(agent) for name, agent in state.agents.items()},
        "events": state.events,
        "proposals": [_to_dict(p) for p in state.proposals],
        "billboard": [_to_dict(b) for b in state.billboard],
        "victory_pitches": [_to_dict(v) for v in state.victory_pitches],
        "archive": state.archive,
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)


def load_state(path: str = config.STATE_FILE) -> Optional[WorldState]:
    """Load WorldState from JSON. Returns None if the file does not exist."""
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    state = WorldState(
        round=data["round"],
        constitution=data.get("constitution", ""),
        events=data.get("events", []),
        archive=data.get("archive", []),
        agents={name: _agent_from_dict(d) for name, d in data.get("agents", {}).items()},
        proposals=[_proposal_from_dict(p) for p in data.get("proposals", [])],
        billboard=[_billboard_from_dict(b) for b in data.get("billboard", [])],
        victory_pitches=[_pitch_from_dict(v) for v in data.get("victory_pitches", [])],
    )
    return state


# ══════════════════════════════════════════════════════════════════════════════
# World-level helpers
# ══════════════════════════════════════════════════════════════════════════════

def log_event(state: WorldState, event_type: str, actor: str, content: str,
              target: Optional[str] = None, location: Optional[str] = None) -> None:
    """Append a structured event to the world event log."""
    state.events.append({
        "round": state.round,
        "type": event_type,
        "actor": actor,
        "target": target,
        "location": location,
        "content": content,
    })


def agents_at(state: WorldState, landmark_key: str) -> List[str]:
    """Return names of all living agents currently at a landmark."""
    return [
        name for name, agent in state.agents.items()
        if agent.is_alive and agent.location == landmark_key
    ]


def distance(a: str, b: str) -> float:
    """Euclidean distance between two landmarks by key."""
    lm_a, lm_b = LANDMARKS.get(a), LANDMARKS.get(b)
    if lm_a is None or lm_b is None:
        return 0.0
    dx = lm_a.coords[0] - lm_b.coords[0]
    dy = lm_a.coords[1] - lm_b.coords[1]
    return (dx ** 2 + dy ** 2) ** 0.5


def resolve_proposals(state: WorldState) -> None:
    """
    Close any open proposals that have been open for PROPOSAL_OPEN_ROUNDS.
    A proposal passes if (votes_for / total_votes) >= PROPOSAL_PASS_THRESHOLD
    and at least one vote was cast.
    """
    for proposal in state.proposals:
        if proposal.status != "open":
            continue
        age = state.round - proposal.round_submitted
        if age < config.PROPOSAL_OPEN_ROUNDS:
            continue
        total = len(proposal.votes_for) + len(proposal.votes_against)
        if total == 0:
            proposal.status = "failed"
        elif len(proposal.votes_for) / total >= config.PROPOSAL_PASS_THRESHOLD:
            proposal.status = "passed"
            log_event(state, "proposal_passed", "system", proposal.title)
        else:
            proposal.status = "failed"
            log_event(state, "proposal_failed", "system", proposal.title)


def apply_energy_decay(state: WorldState) -> None:
    """Reduce every living agent's energy by ENERGY_DECAY_PER_TURN each round."""
    for agent in state.agents.values():
        if not agent.is_alive:
            continue
        agent.energy = max(0.0, agent.energy - config.ENERGY_DECAY_PER_TURN)
        if agent.energy <= config.ENERGY_DEATH_THRESHOLD:
            agent.is_alive = False
            log_event(state, "agent_death", agent.name,
                      f"{agent.name} ran out of energy and died.",
                      location=agent.location)


def award_victory_arch_credits(state: WorldState) -> None:
    """
    At the end of every CREDIT_CYCLE_ROUNDS round, tally Victory Arch pitch
    votes from the current cycle and award credits to the top 3 pitchers.
    """
    cycle_start = state.round - config.CREDIT_CYCLE_ROUNDS
    cycle_pitches = [
        p for p in state.victory_pitches
        if cycle_start < p.round_submitted <= state.round
    ]
    if not cycle_pitches:
        return

    ranked = sorted(cycle_pitches, key=lambda p: len(p.votes), reverse=True)
    for i, reward in enumerate(config.CREDIT_REWARD_TOP3):
        if i >= len(ranked):
            break
        winner_name = ranked[i].author
        if winner_name in state.agents:
            state.agents[winner_name].credits += reward
            log_event(state, "credit_award", "system",
                      f"{winner_name} awarded {reward} credits (pitch rank #{i + 1})")


def new_proposal_id() -> str:
    return "prop_" + uuid.uuid4().hex[:8]


def new_post_id() -> str:
    return "post_" + uuid.uuid4().hex[:8]


def new_pitch_id() -> str:
    return "pitch_" + uuid.uuid4().hex[:8]
