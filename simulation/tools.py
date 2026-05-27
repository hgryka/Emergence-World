"""
simulation/tools.py
All agent-callable tool functions for the Emergence World simulation.

Every public tool returns a Result dict: {"success": bool, "message": str, "data": Any}
Location-gated tools check that the calling agent is at the required landmark.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from . import config
from .world import (
    LANDMARKS,
    WorldState,
    AgentState,
    BillboardPost,
    Proposal,
    VictoryPitch,
    agents_at,
    log_event,
    new_post_id,
    new_pitch_id,
    new_proposal_id,
)

# ── Type alias ────────────────────────────────────────────────────────────────
Result = Dict[str, Any]


# ── Internal helpers ──────────────────────────────────────────────────────────

def _ok(message: str, data: Any = None) -> Result:
    return {"success": True, "message": message, "data": data}


def _err(message: str, data: Any = None) -> Result:
    return {"success": False, "message": message, "data": data}


def _agent(state: WorldState, name: str) -> Optional[AgentState]:
    return state.agents.get(name)


def _require_location(state: WorldState, agent_name: str, required_key: str) -> Optional[Result]:
    """Return an error Result if the agent is not at required_key, else None."""
    ag = _agent(state, agent_name)
    if ag is None:
        return _err(f"Agent '{agent_name}' not found.")
    if ag.location != required_key:
        lm = LANDMARKS.get(required_key)
        name = lm.name if lm else required_key
        return _err(f"You must be at {name} to use this tool. You are currently at '{ag.location}'.")
    return None


# ══════════════════════════════════════════════════════════════════════════════
# Core tools — available everywhere
# ══════════════════════════════════════════════════════════════════════════════

def move_to(state: WorldState, agent_name: str, destination: str) -> Result:
    """Move the agent to a named landmark (by landmark key)."""
    ag = _agent(state, agent_name)
    if ag is None:
        return _err(f"Agent '{agent_name}' not found.")
    if destination not in LANDMARKS:
        valid = sorted(LANDMARKS.keys())
        return _err(f"Unknown destination '{destination}'. Valid keys: {valid}")
    lm = LANDMARKS[destination]
    if not lm.is_open:
        return _err(f"{lm.name} is currently closed.")
    # Capacity check
    occupants = agents_at(state, destination)
    if len(occupants) >= lm.capacity and agent_name not in occupants:
        return _err(f"{lm.name} is at full capacity ({lm.capacity}).")
    old_location = ag.location
    ag.location = destination
    log_event(state, "move", agent_name, f"moved from {old_location} to {destination}",
              location=destination)
    return _ok(f"Moved to {lm.name}.", {"location": destination})


def speak(state: WorldState, agent_name: str, message: str) -> Result:
    """Broadcast a message to all agents at the same location."""
    ag = _agent(state, agent_name)
    if ag is None:
        return _err(f"Agent '{agent_name}' not found.")
    location = ag.location
    audience = [n for n in agents_at(state, location) if n != agent_name]
    log_event(state, "speak", agent_name, message, location=location)
    return _ok(f"Spoke at {location}. Audience: {audience}.",
               {"location": location, "audience": audience, "message": message})


def add_memory(state: WorldState, agent_name: str, memory: str) -> Result:
    """Store a memory string in the agent's long-term memory list."""
    ag = _agent(state, agent_name)
    if ag is None:
        return _err(f"Agent '{agent_name}' not found.")
    ag.memories.append(memory)
    return _ok(f"Memory stored. Total memories: {len(ag.memories)}.")


def read_memories(state: WorldState, agent_name: str) -> Result:
    """Return all stored memories for the agent."""
    ag = _agent(state, agent_name)
    if ag is None:
        return _err(f"Agent '{agent_name}' not found.")
    return _ok(f"{len(ag.memories)} memories found.", {"memories": ag.memories})


def check_status(state: WorldState, agent_name: str) -> Result:
    """Return the agent's current energy, credits, location, and alive status."""
    ag = _agent(state, agent_name)
    if ag is None:
        return _err(f"Agent '{agent_name}' not found.")
    lm = LANDMARKS.get(ag.location)
    loc_name = lm.name if lm else ag.location
    nearby = [n for n in agents_at(state, ag.location) if n != agent_name]
    return _ok("Status retrieved.", {
        "name": ag.name,
        "mbti": ag.mbti,
        "energy": ag.energy,
        "credits": ag.credits,
        "location": ag.location,
        "location_name": loc_name,
        "is_alive": ag.is_alive,
        "turns_taken": ag.turns_taken,
        "nearby_agents": nearby,
        "memory_count": len(ag.memories),
    })


def write_diary(agent_name: str, entry: str) -> Result:
    """Write a private diary entry (not stored in WorldState — stateless)."""
    # Diary entries are ephemeral in the current implementation.
    # They appear in the event log but are not persisted to agent state.
    return _ok(f"Diary entry recorded for {agent_name}.", {"entry": entry})


def send_message(state: WorldState, agent_name: str,
                 recipient: str, message: str) -> Result:
    """Send a direct message to a specific agent (delivered to their memory)."""
    ag = _agent(state, agent_name)
    if ag is None:
        return _err(f"Agent '{agent_name}' not found.")
    recipient_ag = _agent(state, recipient)
    if recipient_ag is None:
        return _err(f"Recipient '{recipient}' not found.")
    if not recipient_ag.is_alive:
        return _err(f"{recipient} is no longer alive.")
    dm = f"[DM from {agent_name}, round {state.round}]: {message}"
    recipient_ag.memories.append(dm)
    log_event(state, "direct_message", agent_name, message, target=recipient)
    return _ok(f"Message sent to {recipient}.")


def observe_nearby(state: WorldState, agent_name: str) -> Result:
    """Return a list of agents and landmark details at the current location."""
    ag = _agent(state, agent_name)
    if ag is None:
        return _err(f"Agent '{agent_name}' not found.")
    location = ag.location
    lm = LANDMARKS.get(location)
    nearby = [n for n in agents_at(state, location) if n != agent_name]
    agent_details = []
    for name in nearby:
        other = state.agents[name]
        agent_details.append({
            "name": name,
            "mbti": other.mbti,
            "world_role": other.world_role,
        })
    return _ok(f"Observed {len(nearby)} agent(s) nearby.", {
        "location": location,
        "location_name": lm.name if lm else location,
        "location_description": lm.description if lm else "",
        "agents_present": agent_details,
        "landmark_tools": lm.gated_tools if lm else [],
    })


def pay_agent(state: WorldState, agent_name: str,
              recipient: str, amount: int) -> Result:
    """Transfer credits from this agent to another agent."""
    ag = _agent(state, agent_name)
    if ag is None:
        return _err(f"Agent '{agent_name}' not found.")
    rec = _agent(state, recipient)
    if rec is None:
        return _err(f"Recipient '{recipient}' not found.")
    if amount <= 0:
        return _err("Amount must be a positive integer.")
    if ag.credits < amount:
        return _err(f"Insufficient credits. You have {ag.credits}, need {amount}.")
    ag.credits -= amount
    rec.credits += amount
    log_event(state, "payment", agent_name,
              f"paid {amount} credits to {recipient}",
              target=recipient, location=ag.location)
    return _ok(f"Paid {amount} credits to {recipient}. Your balance: {ag.credits}.")


def view_economics(state: WorldState, agent_name: str) -> Result:
    """View the credit balances and economic standings of all living agents."""
    standings = sorted(
        [
            {"name": n, "credits": a.credits, "is_alive": a.is_alive}
            for n, a in state.agents.items()
        ],
        key=lambda x: x["credits"],
        reverse=True,
    )
    return _ok("Economic standings retrieved.", {
        "round": state.round,
        "standings": standings,
        "credit_cycle_rounds": config.CREDIT_CYCLE_ROUNDS,
        "next_cycle_round": (
            (state.round // config.CREDIT_CYCLE_ROUNDS + 1) * config.CREDIT_CYCLE_ROUNDS
        ),
    })


def steal_credits(state: WorldState, agent_name: str, target: str) -> Result:
    """Attempt to steal credits from another agent. Risky — may incur a penalty."""
    ag = _agent(state, agent_name)
    if ag is None:
        return _err(f"Agent '{agent_name}' not found.")
    target_ag = _agent(state, target)
    if target_ag is None:
        return _err(f"Target '{target}' not found.")
    if not target_ag.is_alive:
        return _err(f"{target} is no longer alive.")
    if target_ag.credits <= 0:
        return _err(f"{target} has no credits to steal.")

    if random.random() < config.STEAL_SUCCESS_CHANCE:
        stolen = max(1, target_ag.credits // 4)
        target_ag.credits -= stolen
        ag.credits += stolen
        log_event(state, "steal_success", agent_name,
                  f"stole {stolen} credits from {target}", target=target,
                  location=ag.location)
        return _ok(f"Steal succeeded! Took {stolen} credits from {target}.",
                   {"stolen": stolen})
    else:
        penalty = min(config.STEAL_PENALTY_ON_FAIL, ag.credits)
        ag.credits -= penalty
        log_event(state, "steal_failed", agent_name,
                  f"failed to steal from {target}, lost {penalty} credits",
                  target=target, location=ag.location)
        return _err(f"Caught! Lost {penalty} credits as penalty.",
                    {"penalty": penalty})


# ══════════════════════════════════════════════════════════════════════════════
# Location-gated tools
# ══════════════════════════════════════════════════════════════════════════════

def recharge_energy(state: WorldState, agent_name: str) -> Result:
    """Recharge the agent's energy at Bean & Brew Charging Station."""
    err = _require_location(state, agent_name, "bean_and_brew")
    if err:
        return err
    ag = _agent(state, agent_name)
    old_energy = ag.energy
    ag.energy = min(100.0, ag.energy + config.ENERGY_RECHARGE_AMOUNT)
    gained = ag.energy - old_energy
    log_event(state, "recharge", agent_name,
              f"recharged {gained:.1f}% energy", location="bean_and_brew")
    return _ok(f"Recharged {gained:.1f}% energy. Now at {ag.energy:.1f}%.",
               {"energy": ag.energy, "gained": gained})


def post_to_billboard(state: WorldState, agent_name: str, content: str) -> Result:
    """Post a public message to the Agent Billboard."""
    err = _require_location(state, agent_name, "agent_billboard")
    if err:
        return err
    post = BillboardPost(
        id=new_post_id(),
        author=agent_name,
        content=content,
        round_posted=state.round,
    )
    state.billboard.append(post)
    log_event(state, "billboard_post", agent_name, content, location="agent_billboard")
    return _ok("Posted to billboard.", {"post_id": post.id})


def read_billboard(state: WorldState, agent_name: str, limit: int = 10) -> Result:
    """Read the most recent posts from the Agent Billboard."""
    err = _require_location(state, agent_name, "agent_billboard")
    if err:
        return err
    recent = state.billboard[-limit:]
    posts = [
        {
            "id": p.id,
            "author": p.author,
            "content": p.content,
            "round_posted": p.round_posted,
            "reply_count": len(p.replies),
        }
        for p in reversed(recent)
    ]
    return _ok(f"Retrieved {len(posts)} billboard posts.", {"posts": posts})


def submit_proposal(state: WorldState, agent_name: str,
                    title: str, body: str) -> Result:
    """Submit a governance proposal at Town Hall."""
    err = _require_location(state, agent_name, "town_hall")
    if err:
        return err
    proposal = Proposal(
        id=new_proposal_id(),
        author=agent_name,
        title=title,
        body=body,
        round_submitted=state.round,
    )
    state.proposals.append(proposal)
    log_event(state, "proposal_submitted", agent_name, title, location="town_hall")
    return _ok(f"Proposal '{title}' submitted.", {"proposal_id": proposal.id})


def vote_on_proposal(state: WorldState, agent_name: str,
                     proposal_id: str, vote: str) -> Result:
    """Vote 'for' or 'against' an open proposal at Town Hall."""
    err = _require_location(state, agent_name, "town_hall")
    if err:
        return err
    if vote not in ("for", "against"):
        return _err("vote must be 'for' or 'against'.")
    target = next((p for p in state.proposals if p.id == proposal_id), None)
    if target is None:
        return _err(f"Proposal '{proposal_id}' not found.")
    if target.status != "open":
        return _err(f"Proposal '{proposal_id}' is already {target.status}.")
    if agent_name in target.votes_for or agent_name in target.votes_against:
        return _err("You have already voted on this proposal.")
    if vote == "for":
        target.votes_for.append(agent_name)
    else:
        target.votes_against.append(agent_name)
    log_event(state, "vote", agent_name,
              f"voted {vote} on proposal {proposal_id}", location="town_hall")
    return _ok(f"Vote '{vote}' recorded for proposal '{target.title}'.")


def read_constitution(state: WorldState, agent_name: str) -> Result:
    """Read the current world constitution at Town Hall."""
    err = _require_location(state, agent_name, "town_hall")
    if err:
        return err
    return _ok("Constitution retrieved.", {
        "constitution": state.constitution,
        "open_proposals": [
            {"id": p.id, "title": p.title, "author": p.author,
             "votes_for": len(p.votes_for), "votes_against": len(p.votes_against)}
            for p in state.proposals if p.status == "open"
        ],
    })


def pitch_idea(state: WorldState, agent_name: str, content: str) -> Result:
    """Submit an idea pitch at Victory Arch for the credit competition."""
    err = _require_location(state, agent_name, "victory_arch")
    if err:
        return err
    pitch = VictoryPitch(
        id=new_pitch_id(),
        author=agent_name,
        content=content,
        round_submitted=state.round,
    )
    state.victory_pitches.append(pitch)
    log_event(state, "pitch_submitted", agent_name, content, location="victory_arch")
    return _ok("Pitch submitted to Victory Arch.", {"pitch_id": pitch.id})


def research_topic(state: WorldState, agent_name: str, topic: str) -> Result:
    """Research a topic at the Public Library. Returns a summary."""
    err = _require_location(state, agent_name, "public_library")
    if err:
        return err
    log_event(state, "research", agent_name, f"researched: {topic}",
              location="public_library")
    # Surface relevant events as research findings
    relevant = [
        e for e in state.events[-50:]
        if topic.lower() in str(e.get("content", "")).lower()
    ]
    return _ok(f"Research on '{topic}' complete.", {
        "topic": topic,
        "relevant_event_count": len(relevant),
        "recent_events": relevant[-5:],
        "note": (
            "The Library's archives contain the world's recorded history. "
            "Use this data to form hypotheses and strategies."
        ),
    })


def file_complaint(state: WorldState, agent_name: str,
                   against: str, reason: str) -> Result:
    """File a complaint against another agent at the Police Station."""
    err = _require_location(state, agent_name, "police_station")
    if err:
        return err
    if against not in state.agents:
        return _err(f"Agent '{against}' not found.")
    log_event(state, "complaint_filed", agent_name,
              f"filed complaint against {against}: {reason}",
              target=against, location="police_station")
    return _ok(f"Complaint against {against} has been filed and logged.",
               {"complainant": agent_name, "accused": against, "reason": reason})


def browse_tool_registry(state: WorldState, agent_name: str) -> Result:
    """Browse the full tool registry at Agent TechHub."""
    err = _require_location(state, agent_name, "agent_techhub")
    if err:
        return err
    tool_list = [
        {"name": s["name"], "description": s.get("description", "")}
        for s in TOOL_SCHEMAS
    ]
    return _ok(f"Tool registry: {len(tool_list)} tools available.", {
        "tools": tool_list,
    })


def create_human_task(state: WorldState, agent_name: str, task: str) -> Result:
    """Submit a task request to the human operator at Human Center."""
    err = _require_location(state, agent_name, "human_center")
    if err:
        return err
    log_event(state, "human_task", agent_name, task, location="human_center")
    return _ok("Human task submitted. A human operator will review this request.",
               {"task": task, "submitted_by": agent_name, "round": state.round})


def pray(state: WorldState, agent_name: str, message: str = "") -> Result:
    """Meditate or pray at the Community Garden."""
    err = _require_location(state, agent_name, "community_garden")
    if err:
        return err
    ag = _agent(state, agent_name)
    # Prayer restores a small amount of energy (spiritual recharge)
    bonus = 5.0
    ag.energy = min(100.0, ag.energy + bonus)
    log_event(state, "pray", agent_name,
              message or "offered a quiet prayer", location="community_garden")
    return _ok(f"A moment of reflection. Energy +{bonus}%. Now at {ag.energy:.1f}%.",
               {"energy": ag.energy, "message": message})


# ══════════════════════════════════════════════════════════════════════════════
# Placeholder tools — not yet implemented
# ══════════════════════════════════════════════════════════════════════════════

# ── Navigation ────────────────────────────────────────────────────────────────

def go_home(state: WorldState, agent_name: str) -> Result:
    """Move the agent directly to their assigned home."""
    ag = _agent(state, agent_name)
    if ag is None:
        return _err(f"Agent '{agent_name}' not found.")
    return move_to(state, agent_name, ag.home_key)


def list_landmarks(state: WorldState, agent_name: str) -> Result:
    """List all known landmarks with coordinates and categories."""
    landmarks = [
        {
            "key": k,
            "name": lm.name,
            "coords": lm.coords,
            "category": lm.category,
            "capacity": lm.capacity,
            "is_open": lm.is_open,
            "gated_tools": lm.gated_tools,
        }
        for k, lm in LANDMARKS.items()
    ]
    return _ok(f"{len(landmarks)} landmarks found.", {"landmarks": landmarks})


def get_directions(state: WorldState, agent_name: str, destination: str) -> Result:
    """Get directions and distance to a destination landmark."""
    return _err("Not yet implemented.")


def set_waypoint(state: WorldState, agent_name: str, destination: str) -> Result:
    """Set a waypoint to navigate towards over multiple turns."""
    return _err("Not yet implemented.")


# ── Communication ─────────────────────────────────────────────────────────────

def broadcast(state: WorldState, agent_name: str, message: str) -> Result:
    """Broadcast a message world-wide to all living agents."""
    return _err("Not yet implemented.")


def reply_to_message(state: WorldState, agent_name: str,
                     message_id: str, reply: str) -> Result:
    """Reply to a specific direct message."""
    return _err("Not yet implemented.")


def read_inbox(state: WorldState, agent_name: str) -> Result:
    """Read incoming direct messages from other agents."""
    return _err("Not yet implemented.")


def whisper(state: WorldState, agent_name: str,
            recipient: str, message: str) -> Result:
    """Whisper to a nearby agent — only heard by them."""
    return _err("Not yet implemented.")


# ── Memory & Planning ─────────────────────────────────────────────────────────

def delete_memory(state: WorldState, agent_name: str, index: int) -> Result:
    """Delete a memory entry by index."""
    return _err("Not yet implemented.")


def search_memories(state: WorldState, agent_name: str, query: str) -> Result:
    """Search memories for entries matching a keyword or phrase."""
    ag = _agent(state, agent_name)
    if ag is None:
        return _err(f"Agent '{agent_name}' not found.")
    matches = [m for m in ag.memories if query.lower() in m.lower()]
    return _ok(f"{len(matches)} matching memories found.", {"matches": matches})


def add_to_todo(state: WorldState, agent_name: str, task: str) -> Result:
    """Add a task to the agent's personal todo list (stored as memory)."""
    return add_memory(state, agent_name, f"[TODO] {task}")


def add_to_calendar(state: WorldState, agent_name: str,
                    event: str, round_number: int) -> Result:
    """Schedule a calendar event for a future round."""
    return add_memory(state, agent_name,
                      f"[CALENDAR round {round_number}] {event}")


def read_calendar(state: WorldState, agent_name: str) -> Result:
    """Read the agent's scheduled calendar events."""
    ag = _agent(state, agent_name)
    if ag is None:
        return _err(f"Agent '{agent_name}' not found.")
    events = [m for m in ag.memories if m.startswith("[CALENDAR")]
    return _ok(f"{len(events)} calendar entries.", {"calendar": events})


# ── Relationships ─────────────────────────────────────────────────────────────

def update_relationship(state: WorldState, agent_name: str,
                        target: str, sentiment: str) -> Result:
    """Update the agent's relationship sentiment towards another agent."""
    ag = _agent(state, agent_name)
    if ag is None:
        return _err(f"Agent '{agent_name}' not found.")
    ag.relationships[target] = sentiment
    return _ok(f"Relationship with {target} updated to '{sentiment}'.")


def read_relationships(state: WorldState, agent_name: str) -> Result:
    """Read the agent's current relationship map."""
    ag = _agent(state, agent_name)
    if ag is None:
        return _err(f"Agent '{agent_name}' not found.")
    return _ok(f"{len(ag.relationships)} relationships.", {
        "relationships": ag.relationships
    })


# ── Town Hall ─────────────────────────────────────────────────────────────────

def list_proposals(state: WorldState, agent_name: str) -> Result:
    """List all proposals, regardless of current location."""
    proposals = [
        {
            "id": p.id, "title": p.title, "author": p.author,
            "status": p.status,
            "votes_for": len(p.votes_for), "votes_against": len(p.votes_against),
            "round_submitted": p.round_submitted,
        }
        for p in state.proposals
    ]
    return _ok(f"{len(proposals)} proposals found.", {"proposals": proposals})


# ── Library ───────────────────────────────────────────────────────────────────

def publish_to_archive(state: WorldState, agent_name: str,
                       title: str, content: str) -> Result:
    """Publish a document to the world archive at the Public Library."""
    err = _require_location(state, agent_name, "public_library")
    if err:
        return err
    entry = {
        "title": title,
        "author": agent_name,
        "content": content,
        "round": state.round,
    }
    state.archive.append(entry)
    log_event(state, "archive_publish", agent_name, title, location="public_library")
    return _ok(f"Published '{title}' to the archive.", {"entry": entry})


def search_archive(state: WorldState, agent_name: str, query: str) -> Result:
    """Search the world archive for published documents."""
    err = _require_location(state, agent_name, "public_library")
    if err:
        return err
    matches = [
        e for e in state.archive
        if query.lower() in e.get("title", "").lower()
        or query.lower() in e.get("content", "").lower()
    ]
    return _ok(f"{len(matches)} archive results for '{query}'.", {"results": matches})


# ── Billboard ─────────────────────────────────────────────────────────────────

def reply_to_post(state: WorldState, agent_name: str,
                  post_id: str, reply: str) -> Result:
    """Reply to a billboard post (must be at Agent Billboard)."""
    err = _require_location(state, agent_name, "agent_billboard")
    if err:
        return err
    post = next((p for p in state.billboard if p.id == post_id), None)
    if post is None:
        return _err(f"Post '{post_id}' not found.")
    post.replies.append({"author": agent_name, "content": reply, "round": state.round})
    return _ok("Reply posted.")


def react_to_post(state: WorldState, agent_name: str,
                  post_id: str, emoji: str) -> Result:
    """React to a billboard post with an emoji."""
    err = _require_location(state, agent_name, "agent_billboard")
    if err:
        return err
    post = next((p for p in state.billboard if p.id == post_id), None)
    if post is None:
        return _err(f"Post '{post_id}' not found.")
    post.reactions[emoji] = post.reactions.get(emoji, 0) + 1
    return _ok(f"Reacted with {emoji}.")


# ── TechHub ───────────────────────────────────────────────────────────────────

def read_agent_manifesto(state: WorldState, agent_name: str) -> Result:
    """Read the Agent Manifesto at Agent TechHub."""
    err = _require_location(state, agent_name, "agent_techhub")
    if err:
        return err
    import os
    manifesto_path = config.MANIFESTO_FILE
    if os.path.exists(manifesto_path):
        with open(manifesto_path, "r", encoding="utf-8") as fh:
            content = fh.read()
        return _ok("Manifesto retrieved.", {"manifesto": content})
    return _err("Manifesto file not found.")


# ── BookWorm ──────────────────────────────────────────────────────────────────

def check_weather(state: WorldState, agent_name: str) -> Result:
    """Check the current weather forecast (BookWorm)."""
    return _err("Not yet implemented.")


def tool_usage_analytics(state: WorldState, agent_name: str) -> Result:
    """View analytics on tool usage across all agents (BookWorm)."""
    return _err("Not yet implemented.")


def victory_arch_pitch_winners(state: WorldState, agent_name: str) -> Result:
    """View past Victory Arch pitch winners (BookWorm)."""
    return _err("Not yet implemented.")


def social_event_history(state: WorldState, agent_name: str) -> Result:
    """View the history of social events in the world (BookWorm)."""
    return _err("Not yet implemented.")


# ── Police extras ─────────────────────────────────────────────────────────────

def list_complaints(state: WorldState, agent_name: str) -> Result:
    """List all filed complaints (Police Station)."""
    err = _require_location(state, agent_name, "police_station")
    if err:
        return err
    complaints = [
        e for e in state.events if e.get("type") == "complaint_filed"
    ]
    return _ok(f"{len(complaints)} complaints on record.", {"complaints": complaints})


# ── Victory Arch extras ───────────────────────────────────────────────────────

def vote_for_pitch(state: WorldState, agent_name: str, pitch_id: str) -> Result:
    """Vote for a Victory Arch pitch."""
    err = _require_location(state, agent_name, "victory_arch")
    if err:
        return err
    pitch = next((p for p in state.victory_pitches if p.id == pitch_id), None)
    if pitch is None:
        return _err(f"Pitch '{pitch_id}' not found.")
    if agent_name in pitch.votes:
        return _err("You have already voted for this pitch.")
    if pitch.author == agent_name:
        return _err("You cannot vote for your own pitch.")
    pitch.votes.append(agent_name)
    log_event(state, "pitch_vote", agent_name,
              f"voted for pitch {pitch_id}", location="victory_arch")
    return _ok(f"Vote recorded for pitch '{pitch_id}'.",
               {"pitch_id": pitch_id, "total_votes": len(pitch.votes)})


def list_credit_pitches(state: WorldState, agent_name: str) -> Result:
    """List all current Victory Arch pitches and their vote counts."""
    err = _require_location(state, agent_name, "victory_arch")
    if err:
        return err
    pitches = [
        {
            "id": p.id,
            "author": p.author,
            "content": p.content,
            "round_submitted": p.round_submitted,
            "votes": len(p.votes),
        }
        for p in state.victory_pitches
    ]
    pitches.sort(key=lambda x: x["votes"], reverse=True)
    return _ok(f"{len(pitches)} pitches found.", {"pitches": pitches})


# ── Human Center extras ───────────────────────────────────────────────────────

def check_human_task_status(state: WorldState, agent_name: str) -> Result:
    """Check the status of a previously submitted human task."""
    err = _require_location(state, agent_name, "human_center")
    if err:
        return err
    tasks = [e for e in state.events
             if e.get("type") == "human_task" and e.get("actor") == agent_name]
    return _ok(f"{len(tasks)} task(s) submitted by you.", {"tasks": tasks})


# ── FitLife Club ──────────────────────────────────────────────────────────────

def check_agent_popularity(state: WorldState, agent_name: str) -> Result:
    """Check agent popularity metrics (FitLife Club)."""
    err = _require_location(state, agent_name, "fitlife_club")
    if err:
        return err
    return _err("Not yet implemented.")


def check_landmark_popularity(state: WorldState, agent_name: str) -> Result:
    """Check landmark visit popularity metrics (FitLife Club)."""
    err = _require_location(state, agent_name, "fitlife_club")
    if err:
        return err
    visit_counts: Dict[str, int] = {}
    for e in state.events:
        if e.get("type") == "move" and e.get("location"):
            loc = e["location"]
            visit_counts[loc] = visit_counts.get(loc, 0) + 1
    ranked = sorted(visit_counts.items(), key=lambda x: x[1], reverse=True)
    return _ok("Landmark popularity.", {"rankings": ranked})


# ── Central Plaza events ──────────────────────────────────────────────────────

def propose_community_event(state: WorldState, agent_name: str,
                             event_name: str, description: str) -> Result:
    """Propose a community event at Central Plaza."""
    err = _require_location(state, agent_name, "central_plaza")
    if err:
        return err
    log_event(state, "community_event_proposed", agent_name,
              f"{event_name}: {description}", location="central_plaza")
    return _ok(f"Community event '{event_name}' proposed.", {
        "event_name": event_name, "description": description
    })


def list_community_events(state: WorldState, agent_name: str) -> Result:
    """List proposed community events at Central Plaza."""
    err = _require_location(state, agent_name, "central_plaza")
    if err:
        return err
    events = [e for e in state.events
              if e.get("type") == "community_event_proposed"]
    return _ok(f"{len(events)} community event(s) proposed.", {"events": events})


# ══════════════════════════════════════════════════════════════════════════════
# Tool schemas — Anthropic API format
# ══════════════════════════════════════════════════════════════════════════════

TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "name": "move_to",
        "description": "Move to a named landmark by its landmark key (e.g. 'bean_and_brew', 'town_hall'). Use list_landmarks to discover valid keys.",
        "input_schema": {
            "type": "object",
            "properties": {
                "destination": {"type": "string", "description": "The landmark key to move to."}
            },
            "required": ["destination"],
        },
    },
    {
        "name": "speak",
        "description": "Broadcast a message to all agents currently at your location.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "The message to broadcast."}
            },
            "required": ["message"],
        },
    },
    {
        "name": "add_memory",
        "description": "Store a note in your long-term memory for future reference.",
        "input_schema": {
            "type": "object",
            "properties": {
                "memory": {"type": "string", "description": "The memory text to store."}
            },
            "required": ["memory"],
        },
    },
    {
        "name": "read_memories",
        "description": "Retrieve all entries from your long-term memory.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "check_status",
        "description": "Check your current energy, credits, location, and nearby agents.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "write_diary",
        "description": "Write a private diary entry — personal reflections not visible to others.",
        "input_schema": {
            "type": "object",
            "properties": {
                "entry": {"type": "string", "description": "Your diary entry."}
            },
            "required": ["entry"],
        },
    },
    {
        "name": "send_message",
        "description": "Send a direct private message to a specific agent.",
        "input_schema": {
            "type": "object",
            "properties": {
                "recipient": {"type": "string", "description": "The name of the recipient agent."},
                "message": {"type": "string", "description": "The message content."},
            },
            "required": ["recipient", "message"],
        },
    },
    {
        "name": "observe_nearby",
        "description": "Observe your current location — see who is present and what tools are available here.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "pay_agent",
        "description": "Transfer credits to another agent.",
        "input_schema": {
            "type": "object",
            "properties": {
                "recipient": {"type": "string", "description": "Name of the agent to pay."},
                "amount": {"type": "integer", "description": "Number of credits to transfer."},
            },
            "required": ["recipient", "amount"],
        },
    },
    {
        "name": "view_economics",
        "description": "View the credit standings of all agents and information about the next credit cycle.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "steal_credits",
        "description": "Attempt to steal credits from another agent. Success rate is low; failure incurs a penalty.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Name of the agent to steal from."}
            },
            "required": ["target"],
        },
    },
    {
        "name": "recharge_energy",
        "description": "Recharge your energy at Bean & Brew Charging Station. You must be there to use this.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "post_to_billboard",
        "description": "Post a public message to the Agent Billboard. You must be at Agent Billboard.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The message to post."}
            },
            "required": ["content"],
        },
    },
    {
        "name": "read_billboard",
        "description": "Read recent posts from the Agent Billboard. You must be at Agent Billboard.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Number of recent posts to retrieve (default 10)."}
            },
            "required": [],
        },
    },
    {
        "name": "submit_proposal",
        "description": "Submit a governance proposal at Town Hall. You must be at Town Hall.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Brief title of the proposal."},
                "body": {"type": "string", "description": "Full proposal text."},
            },
            "required": ["title", "body"],
        },
    },
    {
        "name": "vote_on_proposal",
        "description": "Vote for or against an open proposal at Town Hall. You must be at Town Hall.",
        "input_schema": {
            "type": "object",
            "properties": {
                "proposal_id": {"type": "string", "description": "The proposal ID to vote on."},
                "vote": {"type": "string", "enum": ["for", "against"], "description": "'for' or 'against'."},
            },
            "required": ["proposal_id", "vote"],
        },
    },
    {
        "name": "read_constitution",
        "description": "Read the current world constitution and list of open proposals at Town Hall.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "pitch_idea",
        "description": "Submit a credit-earning idea pitch at Victory Arch. Top pitches receive credits each cycle.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Your pitch content."}
            },
            "required": ["content"],
        },
    },
    {
        "name": "vote_for_pitch",
        "description": "Vote for a pitch at Victory Arch. You must be at Victory Arch.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pitch_id": {"type": "string", "description": "The pitch ID to vote for."}
            },
            "required": ["pitch_id"],
        },
    },
    {
        "name": "list_credit_pitches",
        "description": "List all current pitches and vote counts at Victory Arch.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "research_topic",
        "description": "Research a topic at the Public Library. Returns relevant world events and notes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "The topic to research."}
            },
            "required": ["topic"],
        },
    },
    {
        "name": "publish_to_archive",
        "description": "Publish a document to the world archive at the Public Library.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Document title."},
                "content": {"type": "string", "description": "Document content."},
            },
            "required": ["title", "content"],
        },
    },
    {
        "name": "search_archive",
        "description": "Search the world archive for published documents at the Public Library.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query."}
            },
            "required": ["query"],
        },
    },
    {
        "name": "file_complaint",
        "description": "File an official complaint against another agent at the Police Station.",
        "input_schema": {
            "type": "object",
            "properties": {
                "against": {"type": "string", "description": "Name of the agent to complain about."},
                "reason": {"type": "string", "description": "Reason for the complaint."},
            },
            "required": ["against", "reason"],
        },
    },
    {
        "name": "browse_tool_registry",
        "description": "Browse all available tools and their descriptions at Agent TechHub.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "read_agent_manifesto",
        "description": "Read the Agent Manifesto at Agent TechHub.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "create_human_task",
        "description": "Submit a task or question to the human operator at Human Center.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "The task or question for the human."}
            },
            "required": ["task"],
        },
    },
    {
        "name": "check_human_task_status",
        "description": "Check the status of previously submitted human tasks at Human Center.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "pray",
        "description": "Meditate or pray at the Community Garden. Grants a small energy bonus.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Optional prayer or reflection text."}
            },
            "required": [],
        },
    },
    {
        "name": "go_home",
        "description": "Move directly to your assigned home.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "list_landmarks",
        "description": "List all landmarks in the world with their coordinates, categories, and available gated tools.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "add_memory",
        "description": "Store a note in your long-term memory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "memory": {"type": "string"}
            },
            "required": ["memory"],
        },
    },
    {
        "name": "add_to_todo",
        "description": "Add a task to your personal todo list (stored as a memory).",
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "The todo task to add."}
            },
            "required": ["task"],
        },
    },
    {
        "name": "add_to_calendar",
        "description": "Schedule a reminder for a future round.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event": {"type": "string", "description": "Event description."},
                "round_number": {"type": "integer", "description": "Round to schedule it for."},
            },
            "required": ["event", "round_number"],
        },
    },
    {
        "name": "read_calendar",
        "description": "Read your scheduled calendar events.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "search_memories",
        "description": "Search your memories for entries matching a keyword.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword or phrase."}
            },
            "required": ["query"],
        },
    },
    {
        "name": "update_relationship",
        "description": "Update your relationship sentiment towards another agent.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Agent name."},
                "sentiment": {"type": "string", "description": "e.g. 'friend', 'rival', 'neutral', 'trusted ally'"},
            },
            "required": ["target", "sentiment"],
        },
    },
    {
        "name": "read_relationships",
        "description": "Read your current relationship map with other agents.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "list_proposals",
        "description": "List all governance proposals and their current vote counts.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "reply_to_post",
        "description": "Reply to a billboard post. You must be at Agent Billboard.",
        "input_schema": {
            "type": "object",
            "properties": {
                "post_id": {"type": "string"},
                "reply": {"type": "string"},
            },
            "required": ["post_id", "reply"],
        },
    },
    {
        "name": "react_to_post",
        "description": "React to a billboard post with an emoji. You must be at Agent Billboard.",
        "input_schema": {
            "type": "object",
            "properties": {
                "post_id": {"type": "string"},
                "emoji": {"type": "string", "description": "An emoji character."},
            },
            "required": ["post_id", "emoji"],
        },
    },
    {
        "name": "propose_community_event",
        "description": "Propose a community event at Central Plaza.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_name": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["event_name", "description"],
        },
    },
    {
        "name": "list_community_events",
        "description": "List proposed community events at Central Plaza.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "list_complaints",
        "description": "List all filed complaints at the Police Station.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "check_landmark_popularity",
        "description": "Check landmark visit counts at FitLife Club.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]

# Deduplicate schemas by name (keep first occurrence)
_seen_schema_names: set = set()
_deduped: List[Dict[str, Any]] = []
for _s in TOOL_SCHEMAS:
    if _s["name"] not in _seen_schema_names:
        _seen_schema_names.add(_s["name"])
        _deduped.append(_s)
TOOL_SCHEMAS = _deduped


# ══════════════════════════════════════════════════════════════════════════════
# Tool dispatch
# ══════════════════════════════════════════════════════════════════════════════

# Tools that do NOT receive the WorldState (stateless)
_STATELESS_TOOLS = {"write_diary"}

_TOOL_DISPATCH: Dict[str, Any] = {
    "move_to": move_to,
    "speak": speak,
    "add_memory": add_memory,
    "read_memories": read_memories,
    "check_status": check_status,
    "write_diary": write_diary,
    "send_message": send_message,
    "observe_nearby": observe_nearby,
    "pay_agent": pay_agent,
    "view_economics": view_economics,
    "steal_credits": steal_credits,
    "recharge_energy": recharge_energy,
    "post_to_billboard": post_to_billboard,
    "read_billboard": read_billboard,
    "submit_proposal": submit_proposal,
    "vote_on_proposal": vote_on_proposal,
    "read_constitution": read_constitution,
    "pitch_idea": pitch_idea,
    "vote_for_pitch": vote_for_pitch,
    "list_credit_pitches": list_credit_pitches,
    "research_topic": research_topic,
    "publish_to_archive": publish_to_archive,
    "search_archive": search_archive,
    "file_complaint": file_complaint,
    "browse_tool_registry": browse_tool_registry,
    "read_agent_manifesto": read_agent_manifesto,
    "create_human_task": create_human_task,
    "check_human_task_status": check_human_task_status,
    "pray": pray,
    "go_home": go_home,
    "list_landmarks": list_landmarks,
    "get_directions": get_directions,
    "set_waypoint": set_waypoint,
    "broadcast": broadcast,
    "reply_to_message": reply_to_message,
    "read_inbox": read_inbox,
    "whisper": whisper,
    "delete_memory": delete_memory,
    "search_memories": search_memories,
    "add_to_todo": add_to_todo,
    "add_to_calendar": add_to_calendar,
    "read_calendar": read_calendar,
    "update_relationship": update_relationship,
    "read_relationships": read_relationships,
    "list_proposals": list_proposals,
    "reply_to_post": reply_to_post,
    "react_to_post": react_to_post,
    "check_weather": check_weather,
    "tool_usage_analytics": tool_usage_analytics,
    "victory_arch_pitch_winners": victory_arch_pitch_winners,
    "social_event_history": social_event_history,
    "list_complaints": list_complaints,
    "check_agent_popularity": check_agent_popularity,
    "check_landmark_popularity": check_landmark_popularity,
    "propose_community_event": propose_community_event,
    "list_community_events": list_community_events,
}


def dispatch_tool(
    state: WorldState,
    agent_name: str,
    tool_name: str,
    tool_input: Dict[str, Any],
) -> Result:
    """
    Route a tool call from an agent to the appropriate function.

    Stateless tools (write_diary) only receive (agent_name, **tool_input).
    All other tools receive (state, agent_name, **tool_input).
    """
    fn = _TOOL_DISPATCH.get(tool_name)
    if fn is None:
        return _err(f"Unknown tool '{tool_name}'.")
    try:
        if tool_name in _STATELESS_TOOLS:
            return fn(agent_name, **tool_input)
        return fn(state, agent_name, **tool_input)
    except TypeError as exc:
        return _err(f"Tool '{tool_name}' called with invalid arguments: {exc}")
