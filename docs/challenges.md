# LauzHack 2026 challenges

Source: https://app.lauzhack.com/Challenges (copied Sat 21 Nov 13:00) + sponsor Discord channels.

## Submission rules (verified)
- ONE project per team (up to 4 people). It can opt into any number of challenges (or none). Every project is in the main ranking.
- Submitted at https://app.lauzhack.com/Participant by ONE person: title (40 chars), short desc (100), long desc (1000), PUBLIC link (GitHub repo with README, code, data), thumbnail (<300 KB), challenge checkboxes. Then invite teammates. Editable later.
- Hard stop Sun 12:00, judging 12:30-15:00. Rule 30: existing code/assets allowed, but the work must be novel and we must say explicitly what is new.
- Eligible for multiple prizes (overall + each challenge).

## Sponsor notes from Discord
- UBS: starter kit, synthetic datasets, scenarios: https://github.com/sschallenges2026/ai-financial-twin-lauzhack-2026 (private; UBS grants access per team: post team name + GitHub logins in #2026-sponsor-ubs).
- AXA: OpenRouter key (USD 10) per team, pitch at their booth or ask in #2026-sponsor-axa. They encourage combining AXA with other challenges.
- Organizers: one Together.AI API key per team at the help desk.
- IMC slides: "IMC at LauzHack 2026.pdf" in #2026-sponsor-imc.

---

LauzHack Main Ranking

Show us your coolest idea! All projects are entered into the main ranking and will be judged first by a subset of our jury, and then by the full jury for selected projects at the closing ceremony.

Logitech

Beyond video conferencing: transform the traditional webcam into the intelligent eyes and ears of AI! We challenge you to create next-generation, context-aware productivity workflows by harnessing real-time multimodal inputs, combining audio, video streams, facial/hand landmarks and other metadata. Can you redefine human-computer interaction?

IMC

The IMChange: Tech for Good challenge is about using technology to solve real-world problems and make a positive difference in people's lives. We're challenging participants to think creatively and develop a working solution that could help a non-profit organisation, particularly in the areas of education, inclusion, or community.

There are plenty of directions you could take. For example, you could build an AI-powered tutor that helps children learn maths in their native language, develop a tool that provides live captions and translations for students with hearing difficulties, or create a platform that connects restaurants with food banks to reduce food waste. Other ideas could include an app that helps people with disabilities navigate public spaces, a platform connecting volunteers with people who need assistance, or an interactive educational game for children from disadvantaged backgrounds.

The possibilities are open-ended, and we encourage participants to find a problem they genuinely care about. The most important thing is to create something practical that could make a real difference. At the end of the hackathon, teams will demonstrate their projects, which will be judged on technical quality, potential social impact, and presentation.

JetBrains

JetBrains Challenge: Cross-Platform Apps with Kotlin Multiplatform

Build with JetBrains Air (recommended) Air isn't mandatory, but using it earns you extra points. Air lets you run AI coding agents side by side in your JetBrains IDE, review their work in one place, and steer them with the IDE's own intelligence. Bring your own agent (Codex, Gemini, GitHub Copilot, Claude, Junie, or any ACP agent) or try Junie Lite for free.

Description Kotlin Multiplatform (KMP) lets you write your app's core logic once and reuse it across Android, iOS, web, or desktop, while keeping the flexibility to go platform-specific where needed. Your challenge: build a cross-platform app with KMP. Explore how shared logic makes development more efficient while still delivering a polished, user-friendly product. It can be impactful (a social good app that supports communities or solves real-world problems) or simple and fun (a to-do list, weather app, or quiz game).

Extra points for:

Dark/light mode
Localization (multi-language support)
Compose Multiplatform for UI
Kotlin backend integration
Shared AI/agent logic: if your idea needs an AI feature, frameworks like Koog let you write it once in commonMain and run it on every platform. Don't force it, but sharing AI logic instead of reimplementing it per platform shows what KMP is for.

Final result: an app running on at least 2 platforms.

Judging Criteria

Implementation and Proof of Concept: does the app run on at least two platforms with working core functionality?
User Experience and Interface: is it polished and native-feeling on each platform?
Technical Features: how much logic is genuinely shared (commonMain) vs. duplicated; use of Compose Multiplatform, backend, localization, or shared AI logic.
Innovation and Creativity: originality of the idea, especially for social good.
Agentic Development Process (extra points, not mandatory): did agents in JetBrains Air do real work while you reviewed and steered them? Extra credit for multi-agent workflows (e.g. different agents on shared and platform-specific code).
Presentation: clarity of the demo, including what was shared and what stayed platform-specific.

Useful Resources

kmp.jetbrains.com - KMP app templates
kotlinlang.org/docs/multiplatform/multiplatform-create-first-app.html - KMP docs
jetbrains.com/compose-multiplatform - Compose Multiplatform
youtu.be/dveR4xWid4Q - Compose Multiplatform Meme Creator tutorial
jetbrains.com/air/ides - JetBrains Air
plugins.jetbrains.com/plugin/33314-air - Air plugin
junie.jetbrains.com - free Junie Lite
docs.koog.ai - Koog agent framework
Nexthink
The problem

Employees lose hours every week to slow or broken work technology, and most of that loss is never reported: a slow VPN, a Teams call that drops, a laptop that takes ten minutes to boot. IT sees only the tip, handling tickets one by one and missing the silent pain that never becomes one.

This is the problem space of Digital Employee Experience (DEX), the category Nexthink defined. Nexthink collects real-time telemetry from devices and apps, asks employees how they feel through in-context surveys, and lets IT fix issues remotely. Spark, Nexthink's AI agent built on Claude, lets employees and IT talk to that data and act on it.

The catch: people only open IT when something is broken. On a good day, nobody thinks of IT, which limits what the agent learns, prevents, and delivers.

The challenge

Build an AI that makes work technology less painful and that employees want to open every day, even when nothing is broken.

It must do two things at once:

Remove real pain. Fix, prevent, or speed up something that wastes people's time.
Agent stickiness. Give the IT agent a new job, trigger, or place to show up, so its value is felt daily, not through notifications alone.

The winning idea makes the agent useful every day in the same way it makes problems go away. A sharp, working idea beats a large feature list. You have 48 hours.

Directions to explore

These are starting points, not a menu. Combine them or ignore them.

Wasted-time finder (employee): slow or repeated web app steps. Daily "time won back" tally and one new shortcut a day.
Talk-me-through-it fixer (employee): broken laptop, app, audio, or VPN. Voice or chat fixes that see your screen and ask before acting.
Past-case finder (IT): solving the same issue from scratch. Morning list of likely tickets with the past fix ready.
Morning device check-up (employee): surprises before a meeting. A 10-second brief with a "fix now?" prompt.
Before-it-breaks predictor (both): issues hitting many people at once. Heads-up on incoming updates or outages.
Personal work-tech coach (employee): unknown features. Weekly growth: "you saved 40 minutes, here is the next habit."
IT's daily cockpit (IT): ticket queues with no context. Daily view of what silently hurts people, ranked by hours lost.
Open lane (anyone): your call.

The strongest entries answer one question: what does the user get from opening it today, if nothing is broken?

Scholé AI
Create a Memorable Learning Experience
The goal

Pick something worth understanding and build the most effective, creative way to teach it. Not a summary and not a chatbot, but a real learning experience that makes the idea click and adapts to the learner in front of it. You choose the topic, so what sets you apart is how you teach it.

Need a starting point? Try teaching Bayes' theorem: "You tested positive. Are you actually sick?" It's there for inspiration, so feel free to pick any topic you like.

How we'll judge

We will reward the cleverness of your approach over the polish of the final product, and we will judge whether it actually teaches someone who has never seen the material. The demo isn’t long enough for a full lesson, so walk us through your approach and show us the moment where the idea clicks.

Resources

There's no dataset or starter code: you're free to use public material, open-source libraries, and any AI models or APIs you like. Scholé mentors will be at our booth throughout the event to help you narrow your topic to something you can build well in the time, point you toward proven teaching methods if you want them, give feedback on your approach, or play the role of a confused learner.

Rules
The learner should never feel like they are just chatting with an AI. AI can power the experience, but a chat window shouldn't be the experience.
Your experience must be different from Scholé’s. Try a Scholé guest lesson here for inspiration, then show us how you’d go beyond it: https://app.schole.ai/g/taste-of-schole
AXA
Frugal use of Multimodal AI

We want to see hacks (== apps, solutions, programs, but not slides!) that use Multimodal AI.

Multimodal = Text + something else. We prefer Text + Images, but we will consider also Text + sound (music, or bird singing, or car noise, or ...) , Text + Movement (see Resources below) , etc.

💡: sometimes, you can transform the other modality into text, e.g. you can use a first model to describe an image, and then have a more intelligent one answer a question. This also qualifies for our challenge, because the important part is the input of your hack ; the processing can be as creative as you want. You could even not use multimodal LLM at all: for example, you want to track birds migrating ; you use traditional image processing to translate patch of image is blue -> 0, patch of image is black -> 1, and then feed the LLM the condensed structure and have it guess the flock type given their arrangement.

Criteria
Real app ?
Slides get a 0.
Jupyter Notebook where you run by hand: 0.2
Jupyter Notebook with widgets: 0.5
Web app: 1
More impressive and polished app with proper user experience: 2
vs AI Slop : we deduct points if there's too much slop and no trace of your own taste, guidance, convictions.
What problem do you solve? Is it relevant? Difficult? Bring something new, or a new angle to something existing.
Technical challenge. Did you just git clone an existing repo and put a different input? Or did you have to make a novel architecture of something ?
Frugality. As you can see in the challenge title, we want you to focus on having an efficient solution / app. Solutions that just throw everything into Fable are heavily discounted compared to those that find creative ways to be efficient.
Team work. Do we have a good feeling everyone contributed a bit ?
Presentation. It's important to present well. To "sell". Also, no "Three axes matter. One of them tells the truth" (see #2).
Resources

Inference keys: we are giving out some keys that you can use on OpenRouter. One per team, $10 budget on each. Thousands of models available. Come to the booth and pitch your idea to get a key. Or write to us on Discord (use the AXA channel, because DMs are often classified as spam because we're not connected and thus I don't get notified about them).

Text + motion : https://teapawt.org/andrew_n_carr/article/2087589706171367537 . Fine-tunes Meta's Glimmer model.

UBS
UBS AI Financial Twin Challenge

Imagine every UBS client has a digital AI twin that understands their financial situation, from spending habits and investments to financial goals, risk profile, and other key financial characteristics.

The challenge is to build an AI-powered Financial Twin that acts as a personalized financial advisor and understands each client’s financial behavior, habits, goals, and risk appetite, and turns this understanding into personalized insights, future scenarios, and smarter financial decisions.

What if I start investing today? Can I afford to buy a house? Am I saving enough for retirement? How could a major life event affect my financial plans? The Financial Twin should help you explore questions like these, understand the potential impact of your choices, and provide guidance tailored to your individual situation and goals.

Be creative! You are free to choose how you bring your Financial Twin to life, whether as a personal AI assistant, a scenario simulator, or any other innovative solution you can imagine.

SBB

Assist customers in case of disruption

Imagine your train is cancelled. You’re standing at the station with one simple question: What should I do now? Usually, someone in a yellow vest can help. But what if no one is around? During rail disruptions, passengers often struggle to understand what an incident means for their personal journey. At the same time, operational teams spend significant effort translating technical disruption information into customer-friendly communication. How can disruption information be transformed into personalized, understandable and actionable guidance for travellers? Your challenge is to design a solution that helps travellers understand the impact of a disruption on their individual journey and supports them in making the right next decision. The solution should be able to:

process disruption and travel information,
identify the impact on a traveller’s journey,
provide clear and relevant recommendations,
communicate in a way that is easy to understand and act upon.

The solution itself is up to you.

Teams are free to explore:

how travellers interact with the solution,
where the information is delivered,
when it should be provided,
and which customer experience creates the greatest value. The solution may be integrated into existing channels, such as mobile apps, chat interfaces, notifications or station services, or propose an entirely new customer experience.

We’re not only interested in what travellers need to know, but how, where and when technology could help them make the best next move.