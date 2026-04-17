# Sophie's World — Newsletter Project

## What this is
A weekly HTML email newsletter for Sophie (Shaun's daughter), generated with Claude and sent automatically each week.

## Sophie's profile
- **Age:** 4th grade (~9–10 years old)
- **Lives:** Fremont, California
- **Family:** Singaporean, living in the USA

**Interests:**
- Gymnastics (active participant) and skiing
- K-pop: especially Katseye and BLACKPINK
- Non-fiction and fun facts ("Weird But True" style)
- Business fairs; learning about saving money

## Newsletter goals
- Develop curiosity about the world
- Age-appropriate current events, including serious topics (wars, economy, tariffs) explained simply with analogies
- Build affinity for both the USA (Fremont/California) and Singapore
- Singapore–USA cultural connection each week

## Newsletter sections (every issue)
| Section | Content |
|---|---|
| **Weird But True** | 2–3 wild fun facts (animals, science, nature) |
| **World Watch** | 2 real, material current events explained for a 4th grader — include serious topics (conflicts, economics) with kid-friendly analogies |
| **Singapore Spotlight** | Something happening in Singapore — culture, food, animals, tech, events |
| **USA Corner** | California/Fremont angle, or US sports/science/culture |
| **K-pop Corner** | BLACKPINK / Katseye news, releases, fun facts |
| **Money Moves** | One saving/entrepreneurship concept + a real kid entrepreneur story |
| **Sophie's Challenge** | A maths or reasoning puzzle tied to that week's World Watch content |

## Format rules
- Language: 4th-grade reading level, warm and fun tone
- Each section gets 1–2 "Learn More" links (pill-style buttons in HTML)
- Links should prefer kid-friendly sources: Time for Kids, NewsForKids.net, Britannica, BBC Newsround, Nat Geo Kids
- Challenge should tie back to World Watch content (percentages, fractions, basic reasoning)
- Footer: "Made with love by Dad & Claude 🤖❤️" + "Fremont, California ↔ Singapore"
- Title format: "Sophie's World · [Date] · Issue #N"

## Repo structure
```
sophies-world/
  CLAUDE.md                        # this file
  newsletters/
    sophies-world-YYYY-MM-DD.html  # one file per issue
  scripts/
    generate.py                    # Claude API generation script (TODO)
    send.py                        # Gmail send script (TODO)
```

## Automation plan (TODO)
- Weekly cron job on Mac Mini
- `generate.py` calls Claude API to research + render HTML newsletter
- `send.py` sends via Gmail SMTP to Sophie's email address
- Triggered every Wednesday or Thursday so it arrives by the weekend
