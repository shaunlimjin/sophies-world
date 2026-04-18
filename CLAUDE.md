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
| **Singapore Spotlight** | A fun fact about Singapore — cultural, historical, economic, nature, food, or quirky. Timeless facts are great; does not need to be current news. |
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
  .env                             # credentials (gitignored)
  .env.example                     # template for credentials
  newsletters/
    sophies-world-YYYY-MM-DD.html  # one file per issue
  scripts/
    generate.py                    # generates newsletter via claude CLI with web search
    send.py                        # sends newsletter via Gmail SMTP
    run.sh                         # wrapper: runs generate + send, logs to logs/run.log
    template.html                  # HTML skeleton with placeholder comments
  tests/
    test_generate.py               # unit tests for generate.py
    test_send.py                   # unit tests for send.py
  logs/
    run.log                        # execution log (gitignored)
```

## Automation
- Cron job on Mac Mini: every Saturday at 6am Pacific
- `run.sh` sets PATH, runs `generate.py && send.py`, appends output to `logs/run.log`
- `generate.py` shells out to `claude -p ... --allowedTools WebSearch,WebFetch --output-format json`
- `send.py` reads `.env` for Gmail credentials and sends via `smtp.gmail.com:587`
- Both scripts are idempotent: `generate.py` skips if today's file exists; `send.py` always sends today's file

## Gmail CSS notes
- Use `display: block` + `margin-bottom` for vertically stacked items — Gmail ignores `flex-direction: column`
- `display: flex; flex-wrap: wrap` is fine for horizontal pill-link rows
