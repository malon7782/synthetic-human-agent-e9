# Product requirements and source notes (checked 2026-10-16)

Sources read directly in Discord:
- Deliverables, edited Oct 14 10:02: https://discord.com/channels/1539111211730468997/1542422765720829963/1542463240691388416
- Submission announcement Oct 12 10:01: https://discord.com/channels/1539111211730468997/1539111292483149924/1559023129924210760
- VM website list Sep 28: https://discord.com/channels/1539111211730468997/1546912338307842089/1554032317809303563
- Devpost: https://ntu-x-st-engineering-hackathon.devpost.com/

The challenge asks for routine desktop activity over a 15-minute session, with variable action timing and visible application workflows. The implementation preserves desktop shortcut launch, visible typing, scrolling, file creation and PowerShell execution. Process ancestry and telemetry authenticity require observation in the target environment; source code alone does not establish them.

Current scope is the program and its usage instructions. Competition submission, report production and video production are outside this implementation.

VM recommended mock websites after organizer certificate setup: https://www.coinmarketcap.com https://www.coursera.org https://www.coinbase.com https://coingecko.com https://www.samsung.com https://aws.amazon.com https://www.amazon.com https://www.apple.com https://apnews.com https://www.dell.com . Do not disable certificate checks or bypass browser warnings.

The implemented browser task visits three recommended sites and scrolls. Hyperlink interaction remains unimplemented. The Hello World task creates and executes a script; it does not claim to implement the challenge's Word/Excel example. See README for supported UI prerequisites and actual validation boundaries.
