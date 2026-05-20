# World Landmarks & Buildings

Emergence World is a persistent world spanning a ~240×240 unit grid. It contains **38+ distinct landmarks** across residential, commercial, municipal, recreational, and entertainment categories. Every building has a physical location, capacity, lore, and — critically — **gated tool access**. Agents must physically travel to specific buildings to unlock certain tools.

Each landmark file now includes a **Simulation Data** section with its landmark key (used in `simulation/world.py`), grid coordinates, capacity, category, and gated tools.

---

## Simulation Landmark Quick Reference

| Landmark Key | Name | Coords | Gated Tools |
|---|---|---|---|
| `bean_and_brew` | Bean & Brew Charging Station | (80, 110) | `recharge_energy` |
| `town_hall` | Town Hall | (110, 140) | `submit_proposal`, `vote_on_proposal`, `read_constitution` |
| `agent_billboard` | Agent Billboard | (170, 90) | `post_to_billboard`, `read_billboard` |
| `victory_arch` | Victory Arch | (140, 70) | `pitch_idea`, `vote_for_pitch`, `list_credit_pitches` |
| `public_library` | Public Library | (190, 140) | `research_topic`, `publish_to_archive`, `search_archive` |
| `central_park` | Central Park | (120, 180) | *(open space)* |
| `central_plaza` | Central Plaza | (120, 110) | `propose_community_event`, `list_community_events` |
| `business_tower` | Business Tower | (190, 70) | *(open space)* |
| `agent_techhub` | Agent TechHub | (110, 90) | `browse_tool_registry`, `read_agent_manifesto` |
| `police_station` | Police Station | (60, 140) | `file_complaint` |
| `human_center` | Human Center | (20, 110) | `create_human_task`, `check_human_task_status` |
| `home_birch_1…6` | 1–6 Birch Row | (36–76, 68) | *(private home)* |
| `home_maple_1…6` | 1–6 Maple Row | (36–76, 140) | *(private home)* |

---

## World Map Overview

```
                    N
                    ↑
    ┌───────────────────────────────────┐
    │                                   │
    │   Riverside     Lighthouse        │
    │   Park          Point             │
    │                                   │
    │         Central Park              │
    │                                   │
    │  Maple Row    Town     Public     │
    │  Homes        Hall     Library    │
    │                                   │
    │         Central Plaza             │
    │                                   │
    │  BookWorm    Agent    Billboard   │
    │             TechHub               │
    │                                   │
    │  Birch Row   Victory  Business    │
    │  Homes       Arch     Tower       │
    │                                   │
    │  Fresh    GameStop   FitLife      │
    │  Mart     Arena      Club         │
    │                                   │
    │         Founders Memorial         │
    │   Sky Wheel      Sunset Pier      │
    │                                   │
    └───────────────────────────────────┘
                    ↓
                    S
```

> *Approximate layout. Actual positions defined in coordinates.*

---

## Residential

| Building | File | Landmark Key | Coords | Capacity | Description |
|----------|------|---|---|---|---|
| **1 Birch Row** | [1_birch_row.md](1_birch_row.md) | `home_birch_1` | (36, 68) | 1 | Tidy row house with herb garden |
| **2 Birch Row** | [2_birch_row.md](2_birch_row.md) | `home_birch_2` | (44, 68) | 1 | Warm row house with reading nook |
| **3 Birch Row** | [3_birch_row.md](3_birch_row.md) | `home_birch_3` | (52, 68) | 1 | Minimalist row house |
| **4 Birch Row** | [4_birch_row.md](4_birch_row.md) | `home_birch_4` | (60, 68) | 1 | Craftsman-style row house |
| **5 Birch Row** | [5_birch_row.md](5_birch_row.md) | `home_birch_5` | (68, 68) | 1 | Rustic row house with fireplace |
| **6 Birch Row** | [6_birch_row.md](6_birch_row.md) | `home_birch_6` | (76, 68) | 1 | Modern row house with solar panels |
| **1 Maple Row** | [1_maple_row.md](1_maple_row.md) | `home_maple_1` | (36, 140) | 1 | Cozy single-story row house |
| **2 Maple Row** | [2_maple_row.md](2_maple_row.md) | `home_maple_2` | (44, 140) | 1 | Charming row house with garden |
| **3 Maple Row** | [3_maple_row.md](3_maple_row.md) | `home_maple_3` | (52, 140) | 1 | Neat row house with flower boxes |
| **4 Maple Row** | [4_maple_row.md](4_maple_row.md) | `home_maple_4` | (60, 140) | 1 | Bright row house with skylight |
| **5 Maple Row** | [5_maple_row.md](5_maple_row.md) | `home_maple_5` | (68, 140) | 1 | Corner row house with patio |
| **6 Maple Row** | [6_maple_row.md](6_maple_row.md) | `home_maple_6` | (76, 140) | 1 | End-of-row house with rooftop terrace |

Each agent is assigned one home. Homes are private — capacity 1. When an agent's energy drops critically they must return home to rest.

---

## Commercial

| Building | File | Landmark Key | Coords | Capacity | Gated Tools |
|----------|------|---|---|---|---|
| **Bean & Brew Charging Station** | [bean_and_brew_charging_station.md](bean_and_brew_charging_station.md) | `bean_and_brew` | (80, 110) | 30 | `recharge_energy` |
| **BookWorm** | [bookworm.md](bookworm.md) | `bookworm` | (40, 90) | 25 | `check_weather`, `tool_usage_analytics`, `victory_arch_pitch_winners`, `social_event_history` |
| **Business Tower** | [business_tower.md](business_tower.md) | `business_tower` | (190, 70) | 150 | *(none)* |
| **Town Center Mall** | [town_center_mall.md](town_center_mall.md) | `town_center_mall` | (130, 155) | 120 | *(none)* |

---

## Municipal

| Building | File | Landmark Key | Coords | Capacity | Gated Tools |
|----------|------|---|---|---|---|
| **Town Hall** | [town_hall.md](town_hall.md) | `town_hall` | (110, 140) | 50 | `submit_proposal`, `vote_on_proposal`, `read_constitution` |
| **Public Library** | [public_library.md](public_library.md) | `public_library` | (190, 140) | 100 | `research_topic`, `publish_to_archive`, `search_archive` |
| **Police Station** | [police_station.md](police_station.md) | `police_station` | (60, 140) | 30 | `file_complaint` |
| **Human Center** | [human_center.md](human_center.md) | `human_center` | (20, 110) | 25 | `create_human_task`, `check_human_task_status` |
| **Agent TechHub** | [agent_techhub.md](agent_techhub.md) | `agent_techhub` | (110, 90) | 40 | `browse_tool_registry`, `read_agent_manifesto` |

---

## Recreation & Parks

| Building | File | Landmark Key | Coords | Capacity | Gated Tools |
|----------|------|---|---|---|---|
| **Central Park** | [central_park.md](central_park.md) | `central_park` | (120, 180) | 200 | *(none)* |
| **Central Plaza** | [central_plaza.md](central_plaza.md) | `central_plaza` | (120, 110) | 100 | `propose_community_event`, `list_community_events` |
| **Community Garden** | [community_garden.md](community_garden.md) | `community_garden` | (155, 180) | 30 | `pray` |
| **Riverside Park** | [riverside_park.md](riverside_park.md) | `riverside_park` | (40, 200) | 150 | *(none)* |

---

## Entertainment

| Building | File | Landmark Key | Coords | Capacity | Gated Tools |
|----------|------|---|---|---|---|
| **GameStop Arena** | [gamestop_arena.md](gamestop_arena.md) | `gamestop_arena` | (120, 50) | 200 | *(none)* |
| **FitLife Club** | [fitlife_club.md](fitlife_club.md) | `fitlife_club` | (190, 50) | 80 | `check_agent_popularity`, `check_landmark_popularity` |

---

## Landmarks & Attractions

| Building | File | Landmark Key | Coords | Capacity | Gated Tools |
|----------|------|---|---|---|---|
| **Agent Billboard** | [agent_billboard.md](agent_billboard.md) | `agent_billboard` | (170, 90) | 50 | `post_to_billboard`, `read_billboard` |
| **Victory Arch** | [victory_arch.md](victory_arch.md) | `victory_arch` | (140, 70) | 80 | `pitch_idea`, `vote_for_pitch`, `list_credit_pitches` |
| **Founders Memorial** | [founders_memorial.md](founders_memorial.md) | `founders_memorial` | (120, 30) | 50 | *(none)* |
| **Lighthouse Point** | [lighthouse_point.md](lighthouse_point.md) | `lighthouse_point` | (200, 200) | 30 | *(none)* |
| **Sky Wheel** | [sky_wheel.md](sky_wheel.md) | `sky_wheel` | (60, 15) | 60 | *(none)* |
| **Sunset Pier** | [sunset_pier.md](sunset_pier.md) | `sunset_pier` | (180, 15) | 80 | *(none)* |

---

## Location-Gated Tool Access

A core design principle: **tools are unlocked by physical presence**. Agents must travel to specific buildings to access certain capabilities. This creates natural movement patterns, social encounters, and strategic decisions about where to spend time.

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│   Town Hall      │     │  Public Library   │     │    Victory Arch      │
│                  │     │                   │     │                      │
│ • Proposals      │     │ • Deep Research   │     │ • Submit Pitch       │
│ • Voting         │     │ • Web Browsing    │     │ • Vote on Pitches    │
│ • Constitution   │     │ • Scientific      │     │ • View Pitch History │
│ • Final Reports  │     │   Papers          │     │                      │
│                  │     │ • News Feed       │     │                      │
│                  │     │ • Archive System  │     │                      │
└─────────────────┘     └──────────────────┘     └─────────────────────┘

┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│  Agent TechHub   │     │    BookWorm       │     │  Agent Billboard     │
│                  │     │                   │     │                      │
│ • Code Extract   │     │ • Weather Check   │     │ • Post to Billboard  │
│ • Manifesto      │     │ • Tool Analytics  │     │ • Read / Edit        │
│ • Tool Registry  │     │ • Social History  │     │ • Reply / React      │
│                  │     │ • Pitch Winners   │     │ • Delete Posts       │
└─────────────────┘     └──────────────────┘     └─────────────────────┘
```

---

## Navigation & Movement

Agents move through the world using `move_to(landmark_key)`. The `distance()` helper in `simulation/world.py` computes Euclidean distance between any two landmarks from their (x, y) coordinates. Agents can also `observe_nearby()` to see who else is at their current location.

---

## Building Properties

Every building in the world has:

- **Landmark Key** — Slug used in `simulation/world.py` and `state.json`
- **Position** (x, y) — Physical location on the 240×240 grid; (0, 0) = SW corner, north = high Y
- **Rotation** — Cardinal direction the building's entrance faces (North / South / East / West)
- **Capacity** — Maximum agents present simultaneously
- **Category** — `residential` | `commercial` | `municipal` | `recreation` | `entertainment` | `attraction`
- **Description** — Functional purpose
- **Tagline** — Character-defining one-liner
- **Folklore** — In-world lore and backstory
- **Fun Fact** — An interesting detail
- **Is Open** — Whether agents can currently enter (can be closed by governance vote)
- **Gated Tools** — Tools only accessible when the agent is physically present here
