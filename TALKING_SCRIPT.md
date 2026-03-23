# 4-Hour Workshop Talking Script
## Agent Communication Protocols: MCP, A2A, and Google ADK
### Building Multi-Agent Systems with MCP, LangGraph & Google ADK

> **How to use this script:** Each slide section starts with the slide number and title, followed by the word-for-word script you can read or paraphrase. `[PAUSE]` means wait for the class. `[ASK CLASS]` means ask the question and wait for responses. `[DEMO]` means switch to your terminal. `[SHOW CODE]` means navigate to the file in your editor. Approximate timing is noted for each section.

---

## PRE-CLASS CHECKLIST (Before students arrive)
- [ ] Terminal open with repo directory: `cd c:\Repos\real-estate-negotiation-simulator`
- [ ] `.env` file has valid `OPENAI_API_KEY`
- [ ] Virtual environment activated: `source venv/bin/activate` (or Windows: `venv\Scripts\activate`)
- [ ] Test MCP servers start: `python m2_mcp/pricing_server.py` → should show "MCP server running"
- [ ] VS Code open with the repo
- [ ] Zoom poll prepared for slide 72
- [ ] Timer ready for breaks (10 min slide 43, 5 min slide 59)

---

## OPENING & HOUSEKEEPING
### *Slides 1–10 | Target: 20 minutes | 0:00–0:20*

---

### SLIDE 1 — Title: "Agent Communication Protocols: MCP, A2A, and Google ADK"
**[~2 min]**

Good morning / good afternoon everyone, and welcome to Week 6 of the Applied Agentic AI program. Today is a big one. This is the class where everything we've been building toward comes together.

The title says "Agent Communication Protocols" — MCP, A2A, and Google ADK. But I want to be honest with you: those are just the names of the tools. What we're actually doing today is answering a much more fundamental question — **how do you build AI agent systems that actually work in production?**

Not agents that work in a notebook demo. Not agents that work when you're showing them to your manager for the first time. Agents that work reliably, at scale, when things go wrong, when the LLM says something unexpected, when the network drops — real production systems.

By the end of today, you will have built — from scratch — a complete multi-agent negotiation system. Two AI agents will negotiate the purchase of a house. They will call real external tools. They will communicate over HTTP. They will terminate correctly. And you will understand exactly why each piece is designed the way it is.

Let's get started.

---

### SLIDE 2 — Introduction: Jeevendra Singh
**[~3 min]**

For those of you who are new, let me do a very quick intro. My name is Jeevendra Singh. I've been a software engineer since 2013 — so about 13 years now. I've worked at Ericsson, SAP, Q2, and for the last four-plus years I've been at Microsoft.

My career has taken me through full-stack development, integration architecture, and for the last few years I've been deeply focused on Generative AI and agentic systems. I've built intelligent API platforms, copilots, and agent orchestration systems professionally — not just in side projects, but as production systems that serve real users.

I've also trained over 2,000 learners through Interview Kickstart on agentic AI, full-stack, data structures, and system design.

I tell you all this not to impress you, but to give you context: everything I'm going to show you today comes from real experience building and shipping these systems. The failures we look at in Module 1 — I've seen versions of those failures in real codebases. The patterns we build toward in Module 4 — those are the patterns that show up in production systems at companies like Microsoft, Google, and Anthropic.

Alright, let's meet each other.

---

### SLIDE 3 — Welcome: Student Introductions
**[~4 min]**

Before we dive in, I want to get a feel for who's in the room. On the slide you see a diagram with a few data points: name, role, location, company.

Let's do a quick round. I'll call on a few of you — just give me your name, what you do, and what you're hoping to get out of today. It doesn't have to be long.

`[ASK CLASS: Call on 3-4 students, get name + role + goal]`

Fantastic. I can see we have a good mix of backgrounds here — data scientists, engineers, people from different industries. That's actually perfect for what we're doing today, because the patterns we're going to learn are applicable across all of those domains. Whether you're building a data pipeline agent, a customer service bot, or a coding assistant — the fundamental problems are the same.

---

### SLIDE 4 — Structure of Class
**[~1 min]**

Quick logistics. Today's session is 4 hours — this is your Sunday live class. After today, there will be an assignment with MCQ and a coding component. You'll want to complete that before the Thursday review session.

The good news: everything you need to do the assignment is in the code we write today. Pay attention during the demos. If something moves fast, we have resources — which brings me to the next slide.

---

### SLIDE 5 — Optimize Your Experience
**[~1 min]**

A few ground rules to make the most of today.

First — **speak up**. This is a live class. If something isn't clear, if I'm moving too fast, if you have a question — put it in the chat or unmute and ask. There are no stupid questions. In my experience, if you're wondering about something, there are five other people wondering the same thing who are too shy to ask.

Second — **do the assignments**. I know it can be tempting to just watch the class and feel like you've learned something. You haven't truly learned it until you've written the code yourself. The assignments are designed to reinforce exactly what we cover today.

Third — **use your resources**. We have a full ecosystem around this class, which the next slide explains.

---

### SLIDE 6 — Don't Worry
**[~30 sec]**

I know the topics today sound intimidating. MCP. A2A. LangGraph. Google ADK. These are all real production technologies that were released in the last 12-18 months. Nobody has been using them for 10 years. Everyone is figuring this out together.

The fact that you're here, learning this now, puts you ahead of most engineers in the industry. So don't worry — we're going to go step by step, and we'll get there together.

---

### SLIDE 7 — IK Support Features
**[~1 min]**

Here's everything available to you outside of this class.

**Uplevel** is your learning platform — all the videos, MCQs, and assignments live there. Make sure you're watching the pre-class videos before each session.

**Post-class videos** will be uploaded after today's session if you need to review anything.

**Technical coaching sessions** are on Wednesdays — if you have questions about the assignment or anything from class, that's your best resource.

**Discord** — I strongly encourage you to use this for peer learning. Some of the best explanations I've seen come from students explaining things to other students.

**TAs** are in the live session to help answer questions in chat.

And **support tickets** on Uplevel for anything technical — if your environment isn't working, open a ticket.

---

### SLIDE 8 — Success Hacks
**[~1 min]**

This slide says "Be patient with yourself" — and I mean that sincerely.

The concepts we're covering today — state machines, MCP protocols, graph-based orchestration, A2A networking — these are not trivial topics. You will not understand everything perfectly after one class. That's completely normal.

The key is: watch the pre-class videos, show up to every class, participate, attempt the assignments even if you don't finish them perfectly, and advocate for yourself when you're stuck.

**Consistency is the key.** One focused hour every day beats six hours of cramming the night before the assignment.

---

### SLIDE 9 — Check Your Email for API Key
**[~2 min]**

This is important. You should have received an email with a dedicated OpenAI API key for this course. The subject line looks something like what's shown on the slide.

If you don't have it, check your spam folder. If it's still not there, reach out to operations at the email on the slide.

A few ground rules for the API key:
- It is for **course-related usage only** — live class and assignments
- **Do not use it for personal projects or commercial work**
- **Do not share it with anyone**
- Keep your costs reasonable — the agents we're building today don't need to run a thousand rounds of negotiation

For today's class, you'll need this key. If you don't have it, you can still follow along with the code walkthrough — just won't be able to run the live demos on your own machine during class.

`[PAUSE: Give people 30 seconds to confirm they have their key]`

---

### SLIDE 10 — Clone & Practice: Your Learning Repository
**[~3 min]**

Alright, let's make sure everyone has the code. The repository is:

`https://github.com/jeev1992/real-estate-negotiation-simulator`

If you haven't cloned it yet:

```
git clone https://github.com/jeev1992/real-estate-negotiation-simulator
cd real-estate-negotiation-simulator
pip install -r requirements.txt
```

Then copy the `.env.example` to `.env` and put your OpenAI API key in there.

The repo has **four complete modules**:
- `m1_baseline` — the naive broken code and the FSM fix
- `m2_mcp` — the MCP servers and clients
- `m3_langgraph_multiagents` — the full LangGraph workflow
- `m4_adk_multiagents` — the A2A and Google ADK implementation

Everything is runnable. Everything has working examples. And everything has exercises with solutions.

`[ASK CLASS: "How many of you have the repo cloned? Give me a thumbs up in chat."]`

Good. If you're still setting it up, keep going — the first 15 minutes of the main content don't require running anything.

---

## WHAT ARE WE BUILDING?
### *Slides 11–15 | Target: 15 minutes | 0:20–0:35*

---

### SLIDE 11 — "What exactly are we building?"
**[~1 min]**

Good question. Let me answer it properly.

We're not building a chatbot. We're not building a RAG pipeline. We're not building a single agent that answers questions.

We're building a **multi-agent system** — two autonomous AI agents who negotiate with each other over the purchase of real estate — without any human in the loop. They decide what to offer, they call external tools to get market data, they reason about strategy, and they reach a deal or walk away. All automatically.

This is the class of problem that's going to define AI engineering for the next five years. Let me show you exactly what I mean.

---

### SLIDE 12 — Problem Statement
**[~4 min]**

Here's the scenario. 742 Evergreen Terrace, Austin TX 78701. Four bedrooms, three bathrooms, 2,400 square feet. Listed at $485,000.

We have two agents, both powered by GPT-4o.

The **Buyer Agent** wants to buy this house for as little as possible. It has a budget ceiling of $460,000 — it literally cannot pay more than that — and it starts by offering $425,000. That's about 12% below asking price. Aggressive but realistic.

The **Seller Agent** wants to sell for as much as possible. It has a floor of $445,000 — it will walk away from anything below that — and it starts by countering at $477,000. It's listed at $485,000 so this is a slight discount off asking.

Now here's the interesting part: there is a **$15,000 zone of agreement**. The buyer's ceiling is $460,000. The seller's floor is $445,000. Any price between $445K and $460K is a deal both sides can accept.

But the buyer doesn't know the seller's floor. The seller doesn't know the buyer's ceiling. They have to negotiate to find out.

This is exactly how real estate negotiations work. And the problem we're solving is: **how do you build a system where these two AI agents reliably reach agreement — or gracefully deadlock — within a bounded number of rounds?**

The naive approach, as we'll see in Module 1, completely fails at this. Let me show you the full architecture first.

---

### SLIDE 13 — Architecture Overview: How Each Layer Solves a Real Problem
**[~7 min]**

This diagram is the roadmap for the entire day. I want you to spend a minute with it before we look at any code — because if you understand this picture, every module we build will feel obvious rather than arbitrary.

Let me tell you a story. Forget all the technology names for a moment.

You want to build something simple: two AI agents that negotiate the price of a house by taking turns. The buyer sends an offer, the seller sends a counter, they go back and forth until one of them agrees or walks away.

How would you build that if you had to do it right now, today, with just Python and an OpenAI API key?

Most people would write something like this: a `while True` loop. Call the buyer, get a response. Call the seller, get a response. Check if either of them said the word "deal". If yes, break. If no, loop again.

That's it. That's the starting point. And it actually runs. You can show it to your manager and it looks like it's working.

`[PAUSE — let that land]`

But the moment you try to use it seriously, four problems hit you, one after another. And each problem is worse than the previous one. That's what our four modules are — four problems, encountered in order, each one invisible until you've solved the one before it.

---

**The first problem you hit: it never stops.**

You run your `while True` loop and notice — sometimes the negotiation just keeps going. The buyer says "I think we're close to a deal." The seller says "I'm almost ready to accept." Neither of them ever says the exact word you're checking for. The loop runs forever. You're spending money on API calls and nothing is happening.

You also realize: even if they do eventually agree, you have no guarantee it happens within a reasonable number of rounds. There's no upper bound. An infinite loop in production isn't just annoying — it's a cost leak and a reliability failure.

**That's what Module 1 fixes.** We introduce a Finite State Machine — a formal way of saying: there are exactly four states this negotiation can be in — not started, in progress, deal reached, or walked away. The last two are what we call terminal states. Once you're in them, there is no next step. The loop cannot continue. Not because we added a break statement — because there is mathematically no transition out. Whether the LLM cooperates or not, the machine terminates.

So after Module 1 we have a negotiation that is guaranteed to end. But what are the agents actually negotiating about?

---

**The second problem: they're arguing about made-up numbers.**

Once termination is solved, you look more carefully at what the agents are saying. And you realize: the buyer's maximum budget is hardcoded in the Python file. The seller's minimum acceptable price is hardcoded in the Python file. Neither agent is using any real market information. The buyer doesn't know what comparable houses in Austin sold for last month. The seller doesn't know what the current market trend is. They're just exchanging numbers based on whatever they were initialized with.

Worse: because both values are in the same Python file, the buyer can technically see the seller's floor price. That's like a real estate negotiation where the buyer can read the seller's private notes. The information asymmetry that makes negotiation interesting doesn't exist.

**That's what Module 2 fixes.** We build two separate data servers — one for market pricing data that both agents can access, and one for the seller's private inventory constraints that only the seller can access. These servers speak a standard protocol called MCP, which means agents can discover what data is available at runtime and call it by name — `get_market_price()`, `get_minimum_acceptable_price()` — instead of reading from hardcoded constants. The buyer genuinely does not know the seller's floor because it is on a server the buyer never connects to. Not a prompt instruction — a physical access boundary.

After Module 2 we have agents that stop reliably and reason about real data. But there's a new problem: coordinating them.

---

**The third problem: two agents, no shared memory, no structure.**

You now have a buyer agent and a seller agent, each capable of calling external tools. How do they actually talk to each other? You go back to your loop: call buyer, pass result to seller, call seller, pass result back to buyer.

But where do you keep track of what round you're on? Where do you store the full history of offers so you can debug what went wrong? What if the buyer sends a message that says "four hundred and thirty thousand" instead of a number — how do you parse that reliably? And if you want to add a third agent — a mediator, say — you have to rewrite the entire loop.

The loop works for two agents in a demo. It doesn't scale.

**That's what Module 3 fixes.** We use LangGraph to model the entire negotiation as a graph — the buyer is a node, the seller is a node, and the edges between them carry routing logic: "if the seller accepted, go to END; otherwise go back to the buyer." All shared data — current round, last offer, full history — lives in a typed state object that every node reads from and writes to. Messages are no longer free-form strings; they're structured objects with a `price` field that must be a number, a `message_type` that must be one of five explicit values. No regex. No guessing.

For the first time, at the end of Module 3, we have a complete running negotiation. Both agents in the same Python process, taking turns, using real data, terminating correctly, with a full audit trail.

But it's still one process. And that matters for the last problem.

---

**The fourth problem: they're too tightly coupled to be real.**

In Module 3, the buyer agent and the seller agent live in the same Python process. The buyer literally imports the seller's code. If you wanted to update the seller's negotiation strategy, you'd have to redeploy the entire system. If you wanted the buyer to be written in TypeScript and the seller in Python, you couldn't do it. If one crashes, both are gone.

In the real world, agents in a production system are independent services. They don't know about each other's implementation. They communicate over a network. They can be deployed, scaled, and updated independently.

**That's what Module 4 fixes.** The seller becomes a real HTTP server. The buyer discovers it by fetching a document called an Agent Card — a standard JSON file that describes what the seller can do and how to talk to it. Offers are sent as HTTP requests. Counter-offers come back as HTTP responses. There's a real network boundary between them. They have no shared memory and no shared code.

Google ADK is the framework that makes running an agent as an HTTP service clean and maintainable — it handles the internal tool-calling loop, session history, and MCP connections automatically. A2A is the protocol that standardizes how agents discover and message each other across that network boundary.

---

So that's the arc. One scenario — two agents negotiating a house — four progressively harder problems, solved in order:

1. Will it stop? → **FSM**
2. Are they reasoning on real data? → **MCP**
3. Can two agents coordinate reliably? → **LangGraph**
4. Can this run in production as independent services? → **A2A + ADK**

Every technology name we use today maps back to one of those questions. When you see "MCP" in Module 2, the question it's answering is "where does the data come from?" When you see "LangGraph" in Module 3, the question it's answering is "how do we coordinate agents without a custom loop?" Keep those questions in your head, and the code will make sense before you've even read it.

`[POINT TO DIAGRAM: "This is why the diagram has 'NAIVE APPROACH FAILS' in the middle with arrows going out to each module — each arrow is one of those four problems."]`

---

### SLIDE 14 — "Let's understand these concepts through a hands-on project"
**[~1 min]**

This is exactly what we're going to do. I could spend 4 hours showing you slides about MCP protocol specifications and LangGraph documentation. But you'd forget 80% of it by tomorrow.

Instead, we're going to build a real system. You're going to see the broken code, understand why it breaks, then build the fix. By the end, you won't just know what MCP is — you'll know why MCP exists, when to use it, and how to wire it into a real agent workflow.

Let's get into Module 1.

---

### SLIDE 15 — Today's Agenda
**[~2 min]**

Here's our roadmap for the day:

**Module 1** — Baseline: Why naive AI agents break, and the FSM fix. This is your foundation. If you don't understand why the naive approach fails, you won't appreciate why the later solutions are designed the way they are.

**Module 2** — Model Context Protocol. How agents access external tools and data without hardcoding anything. We'll build two custom MCP servers.

**Module 3** — LangGraph: Graph-based multi-agent orchestration. This is where we run the full end-to-end negotiation for the first time.

**Module 4** — Google ADK + A2A. This is the production architecture — agents as networked HTTP services, communicating over a standard protocol.

The star in the diagram is on Module 1 right now. That's where we're going next.

---

## MODULE 1: BASELINE — WHY NAIVE AGENTS BREAK
### *Slides 16–29 | Target: 40 minutes | 0:35–1:15*

---

### [BEFORE SLIDE 16] — Show naive_negotiation.py cold
**[~3 min — do this while still on the Agenda slide, before advancing]**

Before I show you the failure modes table, I want you to look at the actual code first — without me explaining anything.

`[OPEN: m1_baseline/naive_negotiation.py in VS Code. Scroll slowly from top to bottom — don't stop, don't comment. Let students read for about 60 seconds.]`

Take a minute. Read through it. Don't worry about understanding every line. Just ask yourself: if someone handed you this code and said "this is running in production handling real estate negotiations" — what would make you nervous? What would you want to fix before you went home for the day?

`[PAUSE — wait for hands or chat responses. Take 3–4 answers. Students will typically spot: the while True, the hardcoded dollar amounts, the string matching for "accept", the fact that prices might be None. Acknowledge each one without explaining it yet.]`

Good. Hold those thoughts — every single thing you just flagged has a name, and slide 16 is going to give you that name.

`[ADVANCE TO SLIDE 16]`

---

### SLIDE 16 — 10 Failure Modes in Naive Agent Systems
**[~5 min]**

I want you to look at this table carefully, because I'm going to ask you to come back to it at the end of Module 4.

We have 10 failure modes in the naive version of our negotiation system. Let me read through them and tell you what each one means in practice.

**Failure 1: Raw string messages.** The agents just exchange plain text. "I'd like to offer $430,000." There are no typed fields, no schema, nothing structured. This means the agent parsing the response has to extract the price from free-form English — which is fragile.

**Failure 2: No schema validation.** Related to #1 — if there's no schema, messages can contain anything. Including garbage. Including `None`. Including the wrong number.

**Failure 3: `while True` loop.** The main negotiation loop is literally `while True:`. There's no state structure. This is the foundation of all the other problems.

**Failure 4: No turn limits.** There is an emergency exit at 100 turns — but that's a band-aid, not a design. It's like saying "if my car's brakes fail, eventually the car will run out of gas." Technically true, but not the kind of guarantee you want.

**Failure 5: Fragile regex.** Look at the root cause column: `r'\$?(\d,]+)+'` — this regex grabs the first number it finds. If the seller says "renovation costs $20,000 and we're countering at $460,000" — the regex grabs $20,000. Instant silent bug.

**Failure 6: No termination guarantee.** The code checks for the string "DEAL" in the seller's response. But "unacceptable" or "no deal" also contain partial matches. And an LLM that says "I think we're almost done" never triggers the check.

**Failure 7: Silent failures.** If regex parsing returns `None`, the negotiation continues using the wrong price — or crashes — with no error message.

**Failure 8: Hardcoded prices.** `LISTING_PRICE = 485_000` is baked into the source code. No live market data. The agents are negotiating about fiction.

**Failure 9: No observability.** You can't reconstruct what happened or why after the fact.

**Failure 10: No evaluation.** You have no way to measure whether the outcome was good or fair.

`[PAUSE]`

I want you to hold onto this table. Every single one of these failures gets fixed in a later module. We'll call them out as we go.

---

### SLIDE 17 — Inside naive_negotiation.py: Key Failure Points
**[~3 min]**

This diagram maps those 10 failures onto the actual code structure. Let me trace through it.

In the center: the `while True` loop. This is ground zero. Everything flows from here.

On the left, the loop-level failures: no schema, while True with no structured states, no history, no evaluation.

In the middle: `NaiveBuyer.respond_to_counter()` and `NaiveSeller.respond_to_offer()`. These are the two agent functions. When they run, they trigger failures 1, 5, 7, and 8 — raw string output, regex grabbing the first number, silent failure on bad parse, hardcoded prices.

On the right: the emergency exit at 100 turns. Which is NOT a termination guarantee — it's a last resort.

The box in the bottom right says "FSM + MCP + LangGraph + A2A fix all 10 failures across 4 modules." That's exactly what we're going to do today.

`[SHOW CODE: Open m1_baseline/naive_negotiation.py in VS Code]`

---

### SLIDE 18 — The Infinite Loop Problem
**[~5 min]**

Let me show you the actual code for the infinite loop problem.

`[SHOW CODE: m1_baseline/naive_negotiation.py, the run_negotiation function]`

```python
def run_negotiation():
    round_num = 1
    while True:   # <<< never exits
        round_num += 1
        buyer_response = buyer_agent(round_num, seller_price)
        buyer_price = extract_price(buyer_response)  # regex, can be None

        seller_response = seller_agent(round_num, buyer_price)
        seller_price = extract_price(seller_response)

        if 'accept' in seller_response.lower():
            break  # <<< only exit, regex could match 'unacceptable'
```

Look at this carefully. `while True:` — no exit condition at the top.

The only `break` is if the word 'accept' appears in the seller's response. But what if the seller says "I cannot accept this offer"? The word 'accept' is there. The loop exits thinking a deal was reached. That's Failure 6.

And look at `extract_price()`:

```python
def extract_price(text):
    match = re.search(r'\$?([\d,]+)', text)
    return float(match.group(1).replace(',', '')) if match else None  # silently None
```

If this returns `None` — which happens any time the LLM doesn't include a clear dollar amount — the negotiation continues with `buyer_price = None`. Whatever GPT does with a `None` price in the next round is undefined behavior. That's Failure 7.

This is what I mean by silent failures. No exception. No log message. Just wrong behavior that's almost impossible to debug after the fact.

---

### SLIDE 19 — Hardcoded Prices & No Validation
**[~4 min]**

Here's the seller agent function from the naive version:

`[SHOW CODE: The seller_agent function]`

```python
ASKING_PRICE = 485_000   # baked in — change requires code edit
MINIMUM_ACCEPTABLE = 445_000   # seller's floor is visible to everyone

def seller_agent(round_num, buyer_price):
    prompt = f"""
    You are a seller. The asking price is ${ASKING_PRICE:,}.
    The buyer just offered ${buyer_price:,}.   # buyer_price could be None!
    Minimum you will accept: ${MINIMUM_ACCEPTABLE:,}.   # leaking floor price!
    Round {round_num} of ... (no limit defined).
    Respond with a counter-offer.
    """
    response = openai_client.chat.completions.create(
        model='gpt-4o',
        messages=[{'role': 'user', 'content': prompt}]
    )
    return response.choices[0].message.content  # raw string, no parsing
```

Count the failures on this one function.

First: `MINIMUM_ACCEPTABLE = 445_000` is a module-level constant. **The buyer's code is in the same file and can see it.** In Module 2, we'll fix this with MCP access control — the seller's floor price is on a server that the buyer simply doesn't connect to.

Second: `buyer_price` could be `None` — there's no validation before it's interpolated into the prompt. GPT sees the string "None" and has to guess what to do.

Third: the `prompt` is a raw f-string. No schema, no structure.

Fourth: `response.choices[0].message.content` — raw string returned. No parsing, no validation.

One function. Four failures.

---

### SLIDE 20 — What Breaks in Production
**[~3 min]**

This diagram maps each failure to the production consequence. Let me walk through the critical ones quickly.

**Floor price leaked** — seller's minimum price is visible to the buyer in the source code. In Module 2, MCP access control fixes this: `get_minimum_acceptable_price()` exists only on the inventory server, which the buyer never connects to.

**None price crash** — `re.search()` returns `None` on mismatch, silently corrupts the data, negotiation continues on wrong data. LangGraph's `NegotiationMessage` TypedDict with a `price: float` field fixes this — `None` can't be stored in a float field.

**String-match accept** — `if 'DEAL' in message.upper()` would match "NO DEAL-BREAKER" — keyword match is easily spoofed. Module 3's typed `message_type: Literal["OFFER", "ACCEPT", "REJECT"]` fixes this.

**No history** — no structured log; can't reconstruct what happened. Module 3's `Annotated[list, operator.add]` history field gives full audit trail.

**Infinite loop** — while True, 100 turn emergency exit, zero chance of deal guaranteed. Module 1's FSM with terminal states fixes this.

Each fix maps to a specific module. That's intentional design.

---

### SLIDE 21 — Finite State Machine: The Fix
**[~5 min]**

Alright. Now that you understand the problem, let me show you the solution for the termination issue: the Finite State Machine.

A Finite State Machine is defined by five things: a finite set of states S, a set of transitions T, an initial state S0, and a set of terminal states F.

The **key property** — and please remember this — is that terminal states have **empty transition sets**. Once you enter a terminal state, there is mathematically no transition that can take you out of it. You cannot leave.

For our negotiation:

```
IDLE ──start()──► NEGOTIATING ──accept()──► AGREED  (terminal, T = {})
                              ──reject()/max_turns──► FAILED  (terminal, T = {})
```

`AGREED` and `FAILED` are terminal states. Their transition sets are empty. Once you're in `AGREED`, there is no edge that leads anywhere. The loop cannot continue.

This is what I mean when I say "termination guarantee." It's not an emergency exit at 100 turns. It's a mathematical property of the state machine's design.

And here's the connection to LangGraph that I want you to keep in mind for Module 3: **LangGraph's `END` node is exactly the same concept.** It's a terminal state at the workflow level. When you add conditional edges to `END`, you're doing the same thing — defining terminal states with empty successor sets.

Why does this matter for AI agents specifically? Because LLMs are non-deterministic. An LLM might never say "DEAL" without a push. The FSM wraps the LLM: regardless of what the LLM outputs, the machine will terminate because `max_turns` provides an outer bound, and `accept()` and `reject()` provide early exits.

---

### SLIDE 22 — Key Design Decisions
**[~3 min]**

Let me walk through the key decisions in the FSM design:

**1. Define all legal states as an enum.** We use Python's `Enum` class — `IDLE`, `NEGOTIATING`, `AGREED`, `FAILED`. This means you can't accidentally create a state called "agreeed" with a typo or "IN_PROGRESS" that you forgot to handle. The compiler catches it.

**2. Define TRANSITIONS as a dict of state → set of reachable next states.** This makes the state machine explicit and inspectable. You can look at the `TRANSITIONS` dict and immediately see that `AGREED` and `FAILED` have empty sets — terminal.

**3. `process_turn()` is simple and bounded.** It increments the turn counter and auto-transitions to `FAILED` when `max_turns` is hit. No complex validation — just an integer that can't grow forever.

**4. `accept()` and `reject()` are guard-first.** Both methods check `is_active` before doing anything. If you call `accept()` after the negotiation is already in `FAILED`, it returns `False` and does nothing. The state can't be corrupted.

The teaching point here is: **provability over pragmatism**. A `while True` loop is simpler to write. But an FSM with an explicit TRANSITIONS map lets you statically verify that every execution path eventually reaches `AGREED` or `FAILED`. That's the foundation of every reliable agent loop.

---

### SLIDE 23 — NegotiationState Enum
**[~4 min]**

`[SHOW CODE: m1_baseline/state_machine.py]`

Let me show you the actual code.

```python
from enum import Enum, auto

class NegotiationState(Enum):
    IDLE        = auto()    # Not started yet
    NEGOTIATING = auto()    # Offers being exchanged
    AGREED      = auto()    # Terminal: deal reached ✓
    FAILED      = auto()    # Terminal: no deal ✗

# The transition table — empty set = terminal (no outgoing transitions)
TRANSITIONS: dict[NegotiationState, set[NegotiationState]] = {
    NegotiationState.IDLE:        {NegotiationState.NEGOTIATING, NegotiationState.FAILED},
    NegotiationState.NEGOTIATING: {NegotiationState.NEGOTIATING,
                                   NegotiationState.AGREED,
                                   NegotiationState.FAILED},
    NegotiationState.AGREED:      set(),   # <<< terminal: no successors
    NegotiationState.FAILED:      set(),   # <<< terminal: no successors
}
```

Look at those empty sets. `NegotiationState.AGREED: set()`. That's it. No transitions. You enter `AGREED`, you stay in `AGREED`. The negotiation loop checks `fsm.is_terminal()` before each iteration and exits if it's in a terminal state.

This is the entire fix for Failures 3, 4, and 6 from our table. One data structure. Three failures fixed.

---

### SLIDE 24 — process_turn(): Bounded Turns
**[~4 min]**

`[SHOW CODE: the process_turn method]`

```python
def process_turn(self) -> bool:
    if not self.is_active:
        return False
    self.context.turn_count += 1
    if self.context.turn_count >= self.context.max_turns:
        self.state = NegotiationState.FAILED
        self.context.failure_reason = FailureReason.MAX_TURNS_EXCEEDED
        return False
    return True
```

This is deliberately simple. There is no complex validation logic, no message type parsing, no exception raising. Just one counter and one cap.

**The key insight:** `turn_count` is an integer. It can only go up. `max_turns` is fixed. So `turn_count >= max_turns` is guaranteed to become true in finite steps. That's the termination proof — not a clever algorithm, just an integer that can't grow forever.

The guard at the top — `if not self.is_active: return False` — means calling `process_turn()` after the negotiation has already ended does nothing. You can't accidentally loop past a terminal state.

Compare this to the naive code where `extract_price()` returns `None` and the loop just… continues. Here, the method returns `False` the moment the cap is hit, and the caller's `while` loop exits cleanly.

---

### SLIDE 25 — Termination Proof
**[~3 min]**

Let me state the formal argument, informally.

**Claim:** every execution of `process_turn()` eventually reaches `AGREED` or `FAILED`.

**Proof:**
- `TRANSITIONS[AGREED] = set()` — once in AGREED, no further transitions are possible
- `TRANSITIONS[FAILED] = set()` — once in FAILED, no further transitions are possible
- `NEGOTIATING → FAILED` when `turn_count >= max_turns` — this is finite by construction
- `accept()` and `reject()` are the only other exits from NEGOTIATING, both leading to terminal states

**Corollary:** the negotiation loop CANNOT run more than `max_turns` iterations.

Why does this matter in production? **Infinite loops burn tokens and money.** An LLM that never says ACCEPT is indistinguishable from a crashed agent. The FSM gives you a hard upper bound on the cost per negotiation session. If each round costs $0.10 in API calls and `max_rounds = 5`, you've bounded the cost at $0.50 per negotiation. No surprises.

---

### SLIDE 26 — NegotiationFSM: Every State, Every Transition, Every Guarantee
**[~3 min]**

This diagram summarizes the complete FSM with the termination proof annotations. Let me point out a few things.

On the left: `IDLE` — not yet started, waiting for first offer.

In the middle: `NEGOTIATING` — the active state. `process_turn()` enforces `turn_count < max_turns`. The only way to stay here is to continue negotiating within the round limit.

Top right: `AGREED` — terminal. Green checkmark. `TRANSITIONS = set()`. Verified by `check_invariants()`: requires `agreed_price` to be set.

Bottom right: `FAILED` — terminal. `TRANSITIONS = set()`. Verified by `check_invariants()`: requires `failure_reason` to be set.

The termination proof in the top center: M is the turn count, strictly decreasing toward max_turns → terminates in finite steps.

This is the foundation everything else builds on.

---

### SLIDE 27 — [DEMO 1] Module 1 Implementation Notes: Agent Fundamentals
**[~8 min]**

We're going to run two demos back to back. The first shows what happens when a deal is possible. The second shows what happens when it isn't. Pay attention to both outcomes — they demonstrate completely different failure modes.

`[DEMO: Switch to terminal]`

**Demo 1a — when a deal is possible:**

```bash
python m1_baseline/naive_negotiation.py
```

`[Let it run. Don't narrate. Wait for the full output including Demo 2.]`

Let's look at Demo 1 first. The negotiation ran and reported a deal. What was the price?

`[PAUSE — wait for someone to read the price from the output]`

`[IF $742 appears:]`

$742. A house listed at $485,000 sold for $742. The system returned `success=True` with no error.

`[Pause 3 seconds]`

Look at the BUG CAUGHT block in the output — it explains exactly what happened. The buyer's opening message mentioned "742 Evergreen Terrace". The seller's response repeated it — "Thank you for your offer on 742 Evergreen Terrace." The regex is `\$?([\d,]+)` — dollar sign is **optional**. It scanned left-to-right, hit `742` in the street address before `$453,150`, and returned 742 as the price. Buyer checked: is $742 under my $460K budget? Yes. Accepted.

No exception. No warning. A contract for $742 on a half-million-dollar house.

`[IF a real price appears — the $742 bug didn't fire this run:]`

Good — we got a real price this time. The output tells us what happened turn by turn. Notice how fragile the path was — the LLM's exact wording determined whether the termination check fired. Run it again and you might get a completely different result.

`[Either way, transition to Demo 2:]`

**Demo 2 — when no deal is possible:**

Now look at Demo 2 in the output below. The buyer's max was $420K and the seller's floor was $450K. There is mathematically no overlap — no price exists that satisfies both sides.

What did the system do?

`[PAUSE — let students read]`

It ran for all 8 turns. Every turn was an LLM call. Every call cost money. Every response was a counter-offer that was never going to close the gap. The emergency exit at turn 8 — which in production is turn 100 — finally stopped it.

This is the core of the infinite loop problem. The code has no concept of "is this negotiation even solvable?" It just keeps going until it hits a hard wall.

`[ASK CLASS: "If the emergency exit was at 100 turns instead of 8, and each turn costs about $0.01 in API calls, what's the cost of one impossible negotiation?" — answer: ~$1. For 1,000 concurrent sessions: $1,000. All wasted.]`

Now let's run the FSM fix and see the contrast:

```bash
python m1_baseline/state_machine.py
```

Every state transition is named and logged. The loop terminates at exactly `max_rounds = 5` — by design, not by emergency. No LLM is called to decide whether to stop. The termination is a mathematical property of the state graph.

`[POINT OUT: "The FSM doesn't fix the $742 price bug — that's Module 3. The FSM doesn't fix the hardcoded prices — that's Module 2. It does exactly one thing: guarantee the loop ends. Each module has exactly one job."]`

---

### SLIDE 28 — Module 1 in One Picture: Before, After, and What's Still Missing
**[~4 min]**

This is your Module 1 summary. Let me walk through it quickly.

**BEFORE** (naive_negotiation.py):
- Hardcoded LISTING_PRICE and SELLER_MIN_PRICE — no live data
- Regex grabs first number — silently returns None on mismatch
- `while True` — no states, no structure
- Emergency exit at 100 turns is a band-aid

**AFTER** (state_machine.py):
- 4 states: IDLE, NEGOTIATING, AGREED, FAILED
- Terminal states have empty TRANSITIONS — mathematically impossible to continue
- `process_turn()` auto-transitions to FAILED at max_turns
- Termination proof: M = (max_turns - turn_count), strictly decreasing → QED

**STILL MISSING — Solved in Later Modules:**
- Hardcoded prices → fixed by Module 2 MCP (`get_market_price()` instead of `LISTING_PRICE = 485_000`)
- Raw strings, no history → fixed by Module 3 LangGraph (`NegotiationMessage` TypedDict, `Annotated[list, operator.add]`)
- No schema, no recovery → fixed by Module 4 A2A (`NegotiationMessage` TypedDict, A2A task-failed response)

The FSM solves exactly what it promises: termination. Everything else is out of scope for Module 1. That's the point — each module has a specific job.

---

### SLIDE 29 — Q&A
**[~5 min]**

Before we move to Module 2, let's take questions on what we just covered.

`[ASK CLASS:]`
- "What questions do you have about the FSM approach?"
- "Does the termination proof make sense?"
- "Is there anything about the code we walked through that wasn't clear?"

Remember: if you're wondering about something, post it in chat or unmute. Others are wondering the same thing.

`[TAKE 3-4 QUESTIONS]`

Great. Let me check the time — we should be around the 1:15 mark. We're right on track. Let's move to Module 2 — MCP.

---

## MODULE 2: MODEL CONTEXT PROTOCOL
### *Slides 30–42 | Target: 35 minutes | 1:15–1:50*

---

### SLIDE 30 — Today's Agenda (Module 2 highlighted)
**[~30 sec]**

Module 1 gave us termination. The FSM guarantees the loop ends. But the agents are still negotiating about hardcoded data. Module 2 fixes that.

We're going to give our agents access to real market data through a standardized protocol — the Model Context Protocol, or MCP.

---

### SLIDE 31 — What Is MCP? (Model Context Protocol)
**[~5 min]**

Let me show you the contrast that makes MCP click.

**Without MCP:**
```
prompt: "The house at 742 Evergreen is worth approximately $450,000."
Problem: hardcoded, stale, unverifiable — agent reasons on fiction
```

**With MCP:**
```
prompt: "You have access to get_market_price(). Call it before making an offer."
LLM calls: get_market_price(address="742 Evergreen Terrace, Austin TX 78701")
Server returns: {"estimated_value": 462000, "comps": [...], "market_trend": "stable"}
LLM: reasons on real, live data
```

That's the difference. Instead of baking data into the prompt, the agent can call external tools at runtime and reason on fresh data.

MCP is how that tool-calling happens in a standardized way. Three operations. That's it:

**1. DISCOVER** — `tools/list` — "What tools do you have?" → returns a list of tool names and descriptions

**2. SCHEMA** — `tool schema` — "What arguments does each tool take?" → JSON Schema per tool

**3. INVOKE** — `tools/call` — "Call `get_market_price(address=...)` " → returns structured result

The LLM sees function signatures, not HTTP endpoints, not business logic. It just sees: "I have a tool called `get_market_price` that takes an address and property type. Let me call it."

That's it. That's MCP.

---

### SLIDE 32 — Key Concepts
**[~3 min]**

A few important properties to understand about MCP:

**Open standard from Anthropic, 2024.** Not proprietary to any one company or framework.

**Transport options: stdio or HTTP/SSE.** When running locally, MCP servers typically run as a subprocess over stdio — the client spawns the server as a child process and communicates over stdin/stdout. For production, you can run MCP servers over HTTP with Server-Sent Events. We'll use both today.

**Protocol: JSON-RPC** with three operations: initialize, list_tools, call_tool.

**ADK wraps MCP automatically via MCPToolset.** In Module 4, you won't write the MCP calls manually — Google ADK's `MCPToolset` handles all the protocol details for you.

**Why MCP vs. direct API calls?**
- **Discoverable** — the agent doesn't need to know about tools at compile time; it discovers them at runtime
- **Reusable across agents** — the same pricing server serves both buyer and seller
- **Access-controlled per agent** — different agents can connect to different servers (critical for the information asymmetry we'll see)
- **Transport-agnostic** — same interface whether local subprocess or remote HTTP
- **Works with any LLM host** — not tied to OpenAI or any specific model

---

### SLIDE 33 — MCP System Architecture
**[~2 min]**

This diagram shows the full MCP ecosystem. On the left: the end user's device — a browser or mobile app, through Claude Desktop or Cursor or any MCP client.

In the middle: the MCP Client (Claude Desktop in this diagram). It talks to an MCP Server via the Model Context Protocol.

On the right: the MCP Server. Notice what it can connect to — Auth 2.0, durable state, workflows, SQL databases, headless browsers, third-party APIs. The MCP server is essentially a capability layer — it translates between the standardized MCP protocol and whatever backend system has the actual data.

In our case, the MCP server is a Python file we write. It exposes our real estate pricing data through the MCP protocol. The agent doesn't know or care that it's a Python file — it just knows it can call `get_market_price()`.

---

### SLIDE 34 — MCP Message Flow
**[~8 min]**

Let me walk through the complete flow using the stdio transport — which is how Module 3 uses MCP.

**Step 1: SPAWN.** The buyer agent (in Python, using `StdioClient`) spawns the MCP server as a subprocess via stdin/stdout pipes. It passes the Python executable path and the server file path.

**Step 2: INITIALIZE.** The client and server do a capabilities handshake. They exchange what they support.

**Step 3: LIST TOOLS.** The client calls `session.list_tools()`. The server returns all tool names with descriptions and input schemas. This is the discovery step.

**Step 4: LLM DECIDES.** GPT-4o is given the tool schemas as function definitions. It decides which tools to call this round — maybe `get_market_price()`, maybe `calculate_discount()`, maybe both.

**Step 5: TOOL CALL.** `session.call_tool("get_market_price", {"address": "742 Evergreen..."})`. The server runs the Python function and returns a structured result.

**Step 6: RESPONSE.** The server result is injected back into the LLM context turn. GPT-4o reasons on the real data and decides its offer price.

**Step 7: FEED BACK.** The tool result is injected into the next LLM context turn.

The entire flow is automated. You write the server function. You tell the LLM it has the tool. The LLM decides when and how to call it. You never hardcode the price.

Before I show you how to BUILD a server, I want to show you this flow live — with a real, production MCP server that GitHub ships. Because the best way to understand the protocol is to see a real client discover a real server's tools without any hardcoding.

`[DEMO: Switch to terminal]`

```bash
cd m2_mcp
python github_agent_client.py
```

`[SHOW OUTPUT: The list of tools GitHub's MCP server exposes — search_repositories, get_file_contents, create_issue, etc.]`

Look at what just happened. Our client connected to GitHub's MCP server — a server we didn't write — and discovered its complete tool catalog. We didn't know ahead of time what tools GitHub supports. We didn't hardcode anything. We ran `list_tools()`, and the server told us everything: tool names, descriptions, parameter schemas.

That's the Discover step from the slide. Right there. Live.

This is exactly what our pricing server will do in a moment — but we'll write it ourselves.

`[PAUSE — let the output sink in]`

---

### SLIDE 35 — MCP Server Anatomy
**[~4 min]**

Now you've seen what discovery looks like from the outside. Let's look at what it takes to BUILD a server that responds to that discovery.

`[SHOW CODE: m2_mcp/pricing_server.py]`

Here's what our pricing server looks like:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP('pricing_server')

@mcp.tool()
def get_market_price(address: str, property_type: str) -> dict:
    """Return market comps and estimated value for a property address."""
    # ... implementation ...
    return {
        'estimated_value': 472000,
        'market_condition': 'balanced',
        'days_on_market': 18,
        'comparable_sales': [...]
    }

@mcp.tool()
def calculate_discount(base_price: float,
                       market_condition: str,
                       days_on_market: int) -> dict:
    """Calculate offer range given market conditions."""
    return {'low': 451000, 'mid': 461000, 'high': 467000}

if __name__ == '__main__':
    mcp.run(transport='stdio')   # ADK spawns this as subprocess
```

Look at how simple this is. One decorator: `@mcp.tool()`. That's it.

The `FastMCP` library reads the Python type hints — `address: str`, `property_type: str` — and automatically generates the JSON Schema that the LLM receives. The docstring becomes the tool description.

You write normal Python. The decorator handles the protocol. The LLM gets a clean, typed interface.

The `mcp.run(transport='stdio')` at the bottom is what ADK calls when it spawns this as a subprocess.

---

### SLIDE 36 — Information Asymmetry via MCP Access
**[~4 min]**

This is one of my favorite design patterns in this entire workshop. Let me explain it carefully.

`[SHOW CODE: m2_mcp/inventory_server.py]`

We have two tools in the inventory server:

```python
# PUBLIC — both buyer and seller can call this
@mcp.tool()
def get_inventory_level(zip_code: str) -> dict:
    return {
        'active_listings': 23,
        'months_of_supply': 2.1,
        'market_pressure': 'seller',
    }

# SELLER ONLY — buyer never connects to this server
@mcp.tool()
def get_minimum_acceptable_price(property_id: str) -> dict:
    return {
        'minimum_price': 445000,
        'reason': 'mortgage payoff',
        'hard_floor': True,
    }
```

The buyer agent connects to the **pricing server only**. It can call `get_market_price()` and `calculate_discount()`.

The seller agent connects to **both** the pricing server and the inventory server. It can call everything the buyer can — plus `get_minimum_acceptable_price()`.

The buyer doesn't know the seller's floor. The seller knows exactly their floor. **This is the information asymmetry that makes the negotiation realistic.**

And here's the key insight: **MCP access control lists are the mechanism for information asymmetry — not prompt text.** In the naive version, we put the seller's floor price in a Python constant visible to everyone. Here, it's behind an MCP endpoint that only the seller's process connects to. The buyer cannot call it — not because the prompt says "you don't know the floor price" — but because the buyer literally has no connection to that server.

This is how information security should work in multi-agent systems.

---

### SLIDE 37 — How LLMs See MCP Tools
**[~2 min]**

`[SHOW CODE: example MCP list_tools response]`

This is what the ADK sends to GPT-4o as function definitions. The JSON Schema is automatically generated from the Python type hints.

```json
{
  "tools": [
    {
      "name": "get_market_price",
      "description": "Return market comps and estimated value for a property address.",
      "inputSchema": {
        "type": "object",
        "properties": {
          "address":       {"type": "string"},
          "property_type": {"type": "string"}
        },
        "required": ["address", "property_type"]
      }
    },
    {
      "name": "calculate_discount",
      // ... schema auto-generated from Python type hints + docstring
    }
  ]
}
```

GPT-4o sees this the same way it sees OpenAI function calling. It decides whether to call the tool based on the description and its reasoning about what information it needs.

The agent doesn't know it's talking to a subprocess over stdin/stdout. It just sees a list of functions it can call. The protocol is invisible.

---

### SLIDE 38 — Connecting to MCP from ADK
**[~3 min]**

`[SHOW CODE: m4_adk_multiagents/buyer_adk.py, the MCPToolset setup]`

Here's how the buyer agent in Module 4 connects to the pricing server:

```python
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset, StdioConnectionParams, StdioServerParameters
)

_PRICING_SERVER = str(Path(__file__).parent.parent / 'm2_mcp' / 'pricing_server.py')

# In BuyerAgentADK.__aenter__:
self._pricing_toolset = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,       # same Python interpreter
            args=[_PRICING_SERVER],       # spawn pricing_server.py
        )
    )
)

# ADK calls list_tools, receives schemas, wraps as LLM function-call tools
tools = await self._pricing_toolset.get_tools()
# tools is now a list of ADK-wrapped MCP Tool objects

self._agent = LlmAgent(
    name='buyer_agent',
    model='openai/gpt-4o',
    tools=tools,          # <<< MCP tools injected here
    instruction=BUYER_INSTRUCTION,
)
```

Three important things here:

1. `MCPToolset` spawns the MCP server as a subprocess using `sys.executable` — the same Python that's running the buyer agent. This ensures version compatibility.

2. `get_tools()` does the list_tools handshake and returns a list of ADK-wrapped tool objects.

3. These tools get injected into `LlmAgent` — from GPT-4o's perspective, they look exactly like regular function calling tools.

You write normal Python. ADK handles the entire MCP protocol.

---

### SLIDE 39 — Seller: Dual MCP Connections
**[~3 min]**

`[SHOW CODE: m4_adk_multiagents/seller_adk.py]`

The seller is slightly more complex because it connects to both servers:

```python
# Toolset 1: pricing (shared with buyer)
self._pricing_toolset = MCPToolset(connection_params=StdioConnectionParams(
    server_params=StdioServerParameters(command=sys.executable,
                                        args=[_PRICING_SERVER])))
pricing_tools = await self._pricing_toolset.get_tools()

# Toolset 2: inventory (SELLER ONLY)
self._inventory_toolset = MCPToolset(connection_params=StdioConnectionParams(
    server_params=StdioServerParameters(command=sys.executable,
                                        args=[_INVENTORY_SERVER])))
inventory_tools = await self._inventory_toolset.get_tools()

# Merge into one list — agent sees all 4 tools as unified
all_tools = pricing_tools + inventory_tools

self._agent = LlmAgent(
    name='seller_agent',
    model='openai/gpt-4o',
    tools=all_tools,       # <<< 4 tools: 2 pricing + 2 inventory
    instruction=SELLER_INSTRUCTION,
)
```

The seller has 4 tools total. The buyer has 2 tools. The seller's extra 2 tools include `get_minimum_acceptable_price()` — its floor price. The buyer has zero path to that information.

---

### SLIDE 40 — [DEMO 2] Module 2 Implementation Notes: MCP Deep Dive
**[~5 min]**

We already saw the Discover step with GitHub's server. Now let's run the server we actually built — and see the full Discover → Schema → Invoke cycle with real pricing data.

`[DEMO: Switch to terminal]`

```bash
# In one terminal: start the SSE server
python m2_mcp/pricing_server.py --transport sse --port 8000

# In another terminal: run the agent client
python m2_mcp/sse_agent_client.py
```

`[SHOW OUTPUT: Tool discovery, then a call to get_market_price()]`

See that? The client discovers our two tools — `get_market_price` and `calculate_discount`. Then it calls `get_market_price("742 Evergreen Terrace, Austin TX 78701", "single_family")` and gets back real structured data — comparable sales, estimated value, market trend.

Compare this to the GitHub demo from earlier. **Same protocol. Same Discover → Schema → Invoke pattern.** The only difference is we wrote this server ourselves in 30 lines of Python using `@mcp.tool()`.

That data — the estimated value, comparable sales, market condition — is what the agents will use in Modules 3 and 4 to justify their offers. No hardcoded prices. Real data, flowing through a protocol.

---

### SLIDE 41 — MCP Error Handling & Cleanup
**[~2 min]**

Quick but important: MCP connections need to be cleaned up properly.

`[SHOW CODE: The async context manager pattern]`

In the buyer and seller agents, we use Python's `async with` pattern — `__aenter__` and `__aexit__`. The `MCPToolset` objects are created in `__aenter__` and cleaned up in `__aexit__`.

This matters because each `MCPToolset` spawns a subprocess. If you don't clean up, you get **orphaned Python processes** running in the background. In production, those processes accumulate and eventually exhaust your system's process table.

The async context manager pattern — `async with BuyerAgentADK(...) as buyer:` — guarantees cleanup even if an exception occurs. This is why the ADK agents are designed as context managers.

---

### SLIDE 42 — Module 2 in One Picture: Two Servers, One Asymmetry, One Protocol
**[~3 min]**

This is your Module 2 summary.

**Pricing Server** — serves both agents. `get_market_price()` and `calculate_discount()`. Returns comparable sales, estimated value. Both buyer and seller call this.

**Inventory Server** — the information asymmetry lives here. `get_inventory_level()` is public — both agents. `get_minimum_acceptable_price()` is seller only — buyer has zero path to this.

**Information Asymmetry box** — "Buyer connects to pricing only. Seller connects to pricing + inventory. Seller knows floor exactly. In production: enforced via MCP OAuth scopes per agent."

**ReAct Planning Pattern** (bottom right): Each round, GPT-4o decides which tools to call, calls them via MCP, uses the result to decide the next offer. This is not hardcoded — the agent decides.

That's the power of MCP: the agent's decision about what data to fetch is as intelligent as its decision about what price to offer.

---

### SLIDE 43 — Time for a Break (10 minutes)
**[~10 min]**

Alright everyone, we've covered Module 1 and Module 2. That's the foundation: termination guarantee and external tool access.

We're going to take a **10-minute break** now. The timer is on the screen.

When we come back, we dive into LangGraph — where we wire all of this together into an actual running negotiation.

Stretch, grab some water, check Slack. Back in 10.

`[START TIMER]`

---

### SLIDE 44 — Q&A
**[~3 min]**

Welcome back. Before we jump to Module 3, let me take any questions on MCP.

`[ASK CLASS:]`
- "Any questions on MCP message flow?"
- "Is the information asymmetry pattern clear — why the buyer literally cannot access the floor price?"
- "Any questions about the stdio vs. SSE transport choice?"

`[TAKE 2-3 QUESTIONS]`

Good. Let's keep moving — Module 3 is where things really get exciting.

---

### SLIDE 45 — Today's Agenda (Module 3 highlighted)
**[~30 sec]**

We have our FSM for termination. We have MCP for external data. Now we need orchestration — a way to wire the buyer and seller agents together into a stateful, observable workflow. That's LangGraph.

---

## MODULE 3: LANGGRAPH MULTI-AGENT ORCHESTRATION
### *Slides 46–57 | Target: 40 minutes | 2:00–2:40*

---

### SLIDE 46 — Why LangGraph Matters
**[~3 min]**

Let me explain why we need LangGraph at all.

After Module 2, we have agents that can call MCP tools. But how do we coordinate two agents taking turns? How do we pass messages between them? How do we track what's happened? How do we make sure the loop terminates?

The naive answer is: write a `while True` loop that calls buyer(), then seller(), checks if they agreed, and breaks if they did.

We just showed you why `while True` is dangerous. More importantly, a custom loop is hard to debug, hard to extend, and hard to observe. When something goes wrong at round 3 of a negotiation, you can't easily reconstruct the state.

LangGraph solves this by modeling the workflow as a **graph**:

- **Nodes** do the work — each node is an async function that calls an agent, processes tools, and returns a state update
- **Edges** control the flow — either unconditional ("always go to seller next") or conditional ("if status == agreed, go to END; otherwise go to buyer")
- **State** stores the shared context — a TypedDict that every node can read and write

Instead of hiding logic inside loops and condition checks, the graph **clearly defines** how the workflow moves from one step to the next.

This makes it explicit, stateful, and easy to extend. Adding a third agent? Add a node and some edges. Adding a mediator? Same thing. With a custom loop, you'd be refactoring everything.

---

### SLIDE 47 — LangGraph Mental Model: From while True to a Declarative Graph
**[~4 min]**

Let me show you this side-by-side comparison, because it's the clearest way to understand what LangGraph does.

**BEFORE — Raw Python:**
```python
while True:
    buyer_response = buyer(msg)
    seller_response = seller(buyer_response)
    if 'DEAL' in msg: break
```
Problems: no shared state, no structured routing, no termination guarantees, can't add 3rd agent.

**AFTER — LangGraph Primitives:**

Three things you need to understand:

**NODES:** Async Python functions. They call LLM, call MCP tools, transform data. They return only the changed fields — not the entire state. This is important: if a node only updates `last_buyer_message`, it returns `{'last_buyer_message': envelope}`. LangGraph merges that into the full state.

**EDGES:** Two types. Unconditional (`START → init → buyer_node`) — always go there. Conditional (`buyer_node → route_after_buyer()`) — a pure function that looks at state and returns a string ("seller_node", "end", etc.).

**STATE:** A `TypedDict` shared by all nodes. Every node reads from it and returns partial updates. The `Annotated[list, operator.add]` field type means "append to this list" rather than overwrite it — that's how you build an audit trail.

Assembled graph: `START → init → buyer → seller → buyer → ... → END`

Guarantees: shared `NegotiationState` TypedDict, conditional routing at every step, full history in state, add 3rd agent = 1 node + 2 edges.

---

### SLIDE 48 — NegotiationMessage TypedDict
**[~4 min]**

`[SHOW CODE: m3_langgraph_multiagents/negotiation_types.py]`

This is one of the most important things in Module 3. The typed message contract.

```python
from typing import TypedDict, Optional, List

class NegotiationMessage(TypedDict, total=False):
    message_id:           str              # UUID, unique per message
    session_id:           str              # ties all rounds together
    round:                int              # 1-indexed round counter
    from_agent:           str              # 'buyer' | 'seller'
    to_agent:             str              # 'buyer' | 'seller'
    message_type:         str              # 'OFFER' | 'COUNTER_OFFER' | 'ACCEPT' | 'REJECT' | 'WITHDRAW'
    price:                Optional[float]  # ALWAYS a number, never a string
    message:              str              # human-readable text
    conditions:           List[str]        # e.g. ['inspection', 'financing']
    closing_timeline_days: Optional[int]
    reasoning:            Optional[str]    # agent's internal notes
    in_reply_to:          Optional[str]    # message_id of previous message
```

Compare this to the naive code: `return response.choices[0].message.content` — a raw string.

Here, `price` is `Optional[float]`. The agent cannot return the string "four hundred and fifty thousand dollars." It must return a float, or `None`. Regex #5 is dead.

`message_type` is one of five explicit values. The agent cannot return "I think we might be close to a deal" as a message type. It must choose from the enum. String-match accept failure #6 is dead.

`message_id` and `in_reply_to` give you a message thread. `round` ties messages to the negotiation timeline. `session_id` ties the whole negotiation together.

This single TypedDict fixes Failures 1, 2, and 5 from our table.

Factory functions make it easy to create valid messages:
```python
create_offer(session_id, round, price, conditions) → NegotiationMessage
create_acceptance(session_id, round, price) → NegotiationMessage
```

---

### SLIDE 49 — NegotiationState TypedDict
**[~4 min]**

`[SHOW CODE: m3_langgraph_multiagents/langgraph_flow.py, the NegotiationState class]`

```python
import operator
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, END

class NegotiationState(TypedDict):
    session_id:           str
    round:                int
    status:               str   # 'negotiating' | 'agreed' | 'failed'
    last_buyer_message:   dict
    last_seller_message:  dict

    # Annotated[list, operator.add] means APPEND, not overwrite
    history: Annotated[list[dict], operator.add]

    # Agent references (set during init)
    _buyer_agent_ref:  object
    _seller_agent_ref: object
```

The key line is `history: Annotated[list[dict], operator.add]`.

Without `Annotated`: every time a node returns `{'history': [new_item]}`, LangGraph **replaces** the history list with `[new_item]`. You lose all previous history.

With `Annotated[list, operator.add]`: LangGraph **appends** `new_item` to the existing history. Every message ever sent is preserved.

This is LangGraph's reducer pattern. `operator.add` on lists means concatenation. You can define custom reducers — for example, `keep_last_10` that only retains the 10 most recent messages.

```python
def buyer_node(state: NegotiationState) -> dict:
    envelope = ...  # call buyer agent
    return {
        'last_buyer_message': envelope,
        'round': state['round'] + 1,
        'history': [envelope],  # <<< APPENDED, not overwritten
    }
```

This is how you get a complete audit trail with zero extra code. Every node returns its update. LangGraph merges all updates into the shared state using the reducers.

---

### SLIDE 50 — Graph Nodes: buyer_node & seller_node
**[~4 min]**

`[SHOW CODE: langgraph_flow.py, the buyer_node function]`

```python
async def buyer_node(state: NegotiationState) -> dict:
    """LangGraph node: buyer agent takes one turn."""
    async with BuyerAgentADK(session_id=state['session_id']) as buyer:
        if state['round'] == 1:
            envelope = await buyer.make_initial_offer_envelope()
        else:
            envelope = await buyer.respond_to_counter_envelope(
                state['last_seller_message']
            )

    msg_type = envelope.get('message_type', 'OFFER')
    new_status = 'failed' if msg_type == 'WITHDRAW' else state['status']

    return {
        'last_buyer_message': envelope,
        'round': state['round'] + 1,
        'status': new_status,
        'history': [{'turn': 'buyer', 'round': state['round'], **envelope}],
    }
```

Three things to notice:

1. **`async with BuyerAgentADK(...) as buyer:`** — this is the context manager that starts and stops MCP subprocesses for each turn. Clean resource management.

2. **Round 1 special case** — first turn makes an initial offer; all subsequent turns respond to the seller's counter. The state tells the node which case it's in.

3. **Returns partial state** — only the fields that changed. LangGraph merges this into the full state. The node doesn't need to return the full 10-field TypedDict.

The `seller_node` is symmetric — it calls `SellerAgentADK.respond_to_offer_envelope()` and updates `last_seller_message`.

---

### SLIDE 51 — Conditional Edges: Routing Logic
**[~4 min]**

`[SHOW CODE: the route_after_buyer and route_after_seller functions]`

```python
def route_after_buyer(state: NegotiationState) -> str:
    """Decide what node runs after buyer takes a turn."""
    if state['status'] in ('agreed', 'failed'):
        return 'end'
    msg_type = state['last_buyer_message'].get('message_type', '')
    if msg_type == 'WITHDRAW':
        return 'end'
    if state['round'] > MAX_ROUNDS:
        return 'end'   # round limit hit
    return 'seller_node'   # continue to seller

def route_after_seller(state: NegotiationState) -> str:
    """Decide what node runs after seller takes a turn."""
    if state['status'] in ('agreed', 'failed'):
        return 'end'
    msg_type = state['last_seller_message'].get('message_type', '')
    if msg_type in ('ACCEPT', 'REJECT'):
        return 'end'
    if state['round'] > MAX_ROUNDS:
        return 'end'
    return 'buyer_node'   # continue to buyer
```

This is the declarative routing that replaces your `if/elif` chains inside a `while True` loop.

Pure functions — no side effects. They read state, they return a string. LangGraph uses that string to pick the next node.

The `return 'end'` lines route to LangGraph's `END` node — the terminal state, just like the FSM's `AGREED` and `FAILED`. `END` has no outgoing edges. The graph stops.

Notice: there are six different conditions that lead to `'end'`. That would be six `break` statements scattered through a `while True` loop — easy to miss one. Here, they're all visible in one place.

---

### SLIDE 52 — Wiring the Graph
**[~3 min]**

`[SHOW CODE: create_negotiation_graph() function]`

```python
from langgraph.graph import StateGraph, END

def create_negotiation_graph() -> StateGraph:
    graph = StateGraph(NegotiationState)

    # Register nodes
    graph.add_node('buyer_node',  buyer_node)
    graph.add_node('seller_node', seller_node)

    # Entry point
    graph.set_entry_point('buyer_node')

    # Conditional edges (routing functions decide next node)
    graph.add_conditional_edges(
        'buyer_node',
        route_after_buyer,
        {'seller_node': 'seller_node', END: END}
    )
    graph.add_conditional_edges(
        'seller_node',
        route_after_seller,
        {'buyer_node': 'buyer_node', END: END}
    )

    return graph.compile()   # returns CompiledStateGraph

# Run it:
compiled = create_negotiation_graph()
final_state = await graph.ainvoke(initial_state)
```

This is the complete graph assembly. Seven lines of meaningful code. Compare that to a custom `while True` loop with scattered conditions.

`graph.compile()` validates the graph structure — it catches things like unconnected nodes or missing edge definitions at startup, not at runtime.

`graph.ainvoke(initial_state)` runs the graph until it hits `END` and returns the final state. One call. The entire negotiation.

---

### SLIDE 53 — Annotated Reducers: Deep Dive
**[~3 min]**

`[SHOW CODE: the annotated reducer examples]`

Let me make sure the reducer concept is completely clear, because it trips people up.

```python
# WITHOUT Annotated — each node OVERWRITES the list
class BrokenState(TypedDict):
    history: list   # node returns {'history': [new_item]}
                    # LangGraph sets state.history = [new_item]
                    # Previous items are LOST

# WITH Annotated — LangGraph MERGES using the reducer
class CorrectState(TypedDict):
    history: Annotated[list, operator.add]
                    # node returns {'history': [new_item]}
                    # LangGraph does state.history = state.history + [new_item]
                    # Previous items are PRESERVED
```

For our negotiation, this means: every offer, every counter-offer, every acceptance is preserved in `history`. At the end of the negotiation, `final_state['history']` contains the complete transcript of every message that was sent.

You can also define **custom reducers**:

```python
def keep_last_10(old: list, new: list) -> list:
    return (old + new)[-10:]

class WindowedState(TypedDict):
    history: Annotated[list, keep_last_10]  # sliding window of 10 messages
```

This is useful for long-running agents where you don't want to grow state indefinitely.

---

### SLIDE 54 — Running the LangGraph Negotiation
**[~3 min]**

`[SHOW CODE: m3_langgraph_multiagents/main_langgraph_multiagent.py]`

```python
import asyncio, uuid
from m3_langgraph_multiagents.langgraph_flow import create_negotiation_graph

async def main():
    graph = create_negotiation_graph()

    initial_state = {
        'session_id': str(uuid.uuid4()),
        'round': 1,
        'status': 'negotiating',
        'last_buyer_message':  {},
        'last_seller_message': {},
        'history': [],
    }

    final_state = await graph.ainvoke(initial_state)

    print(f'Final status: ', final_state['status'])
    print(f'Rounds completed: ', final_state['round'] - 1)
    print(f'History entries: ', len(final_state['history']))

    if final_state['status'] == 'agreed':
        price = final_state['last_seller_message'].get('price', 0)
        print(f'Deal reached at: ${price:,}')

asyncio.run(main())
```

That's the entire entry point. Create the graph, create the initial state, invoke, print results.

The graph runs until it hits `END`. The final state has the complete history, the final status, and the agreed price if there was one.

---

### SLIDE 55 — LangGraph Negotiation Graph: Full Diagram
**[~3 min]**

This is the complete picture of what we just built. Let me walk through it one final time.

**START** → unconditional edge → **INIT NODE** — creates BuyerAgent and SellerAgent, sets initial state, runs exactly once.

**BUYER NODE** — Round 1: `make_initial_offer()`. Round 2+: `respond_to_counter()`. Calls MCP tools via ADK. Calls GPT-4o. Returns partial state update.

**`route_after_buyer()`** — checks `status`, `message_type`, `round_number`. Routes to `seller_node` or `END`.

**SELLER NODE** — `respond_to_offer()`. Calls MCP tools via ADK — pricing AND inventory. Calls GPT-4o. Returns partial state update.

**`route_after_seller()`** — same logic, routes to `buyer_node` or `END`.

**END** — no outgoing edges. Termination guaranteed. Same as FSM terminal state.

All nodes read from the shared `NegotiationState`. The `history` field grows with every turn via `operator.add`. You get full observability for free.

**Still missing — Module 4:** Both agents are in the same process. No independent deployment. No network boundary. No A2A + ADK across HTTP.

---

### SLIDE 56 — [DEMO 3] Module 3 Implementation Notes: LangGraph
**[~5 min]**

Let's run it.

`[DEMO: Switch to terminal]`

```bash
python m3_langgraph_multiagents/main_langgraph_multiagent.py
```

`[SHOW OUTPUT as it runs — point out each round]`

Watch this carefully. You'll see:
- Round 1: Buyer makes an opening offer around $425K
- Round 1 response: Seller counters around $477K — it called the pricing server AND the inventory server
- Round 2: Buyer increases offer — it consulted market data
- Rounds continue until agreement or deadlock

`[HIGHLIGHT: "Notice the seller accepted — look at the price. It's somewhere between $445K and $460K. That's the zone of agreement. The negotiation worked."]`

`[SHOW: final_state['history'] — the complete audit trail]`

Look at this — every single message, with timestamps, round numbers, prices, message types. All captured automatically by the `Annotated[list, operator.add]` reducer. No extra logging code.

This is what observability looks like in a well-designed multi-agent system.

---

### SLIDE 57 — Module 3 in One Picture: Four Files, One Graph, Full Observability
**[~3 min]**

This summary diagram shows all four files working together:

**`negotiation_types.py`** — the typed contract. `NegotiationMessage` TypedDict. Fixes raw strings, no validation, fragile parsing.

**`langgraph_flow.py`** — the StateGraph. Conditional routers, the `NegotiationState` with `Annotated` history. Fixes while True, no shared state, no observability.

**Buyer Node** — calls `_plan_mcp_tools_calls()` via ReAct. MCP calls pricing. GPT-4o → offer decision.

**Seller Node** — calls `get_minimum_acceptable_price()` via inventory. MCP pricing + inventory. GPT-4o → counter decision.

**Still missing for Module 4:** Both agents in same process. No independent deployment. Module 4 adds A2A + ADK across HTTP.

---

## Q&A + BREAK
### *Slides 58–59 | ~10 minutes*

---

### SLIDE 58 — Q&A
**[~5 min]**

Excellent work. We've now built a complete, running multi-agent negotiation system. Two agents, MCP tools, LangGraph orchestration, full observability.

`[ASK CLASS:]`
- "What questions do you have about LangGraph's graph structure?"
- "Is the conditional routing clear — why we use routing functions instead of if/else in the nodes?"
- "Is the annotated reducer pattern clear?"

`[TAKE 3-4 QUESTIONS]`

One thing I want to re-emphasize: the LangGraph approach fixes exactly the problems we identified in Module 1. The FSM gave us termination at the agent level. LangGraph gives us termination at the workflow level — via the `END` node and conditional edges. They're the same concept at different scales.

---

### SLIDE 59 — Time for a Break (5 minutes)
**[~5 min]**

Short 5-minute break. We have one more module — the big one.

When we come back, we're going to take everything we've built and make it production-grade. The buyer and seller agents are going to run as independent HTTP services. They're going to discover each other via a standard protocol. They're going to communicate over a network boundary.

This is Google ADK and the A2A protocol. Back in 5.

`[START TIMER]`

---

## MODULE 4: GOOGLE ADK + A2A PROTOCOL
### *Slides 60–75 | Target: 55 minutes | 2:55–3:50*

---

### SLIDE 60 — Today's Agenda (Module 4 highlighted)
**[~30 sec]**

Welcome back. Final module. This is where we go from "a working multi-agent system" to "a production-grade multi-agent system."

The key shift: in Module 3, both agents ran in the same Python process. They shared memory. The buyer could theoretically import the seller's code. In Module 4, they run as **independent HTTP services** with a network boundary between them.

---

### SLIDE 61 — Google ADK: What It Provides
**[~4 min]**

Google ADK — the Agent Development Kit — is a framework layer that provides four abstractions so you don't have to write them yourself.

**LlmAgent** — defines the agent: model, instructions, tools, name. This is your agent's "personality and capabilities" in one object.

**Runner** — executes the agent. It manages the tool-call loop. When GPT-4o says "I want to call `get_market_price()`", the Runner executes that call via MCPToolset, injects the result back into the context, and calls GPT-4o again. You never write this loop manually.

**InMemorySessionService** — stores conversation history across turns, keyed by session_id. Every time you call `runner.run_async()`, it loads the conversation history, runs the turn, and saves the updated history. You never manage session state manually.

**MCPToolset** — connects to MCP servers, calls `list_tools()`, wraps the tools as LLM function-call definitions, and handles all call_tool invocations. You never write MCP protocol code manually.

The bottom note on the slide is critical: **"ADK orchestrates the inner loop: LlmAgent decides a tool call → Runner executes it via MCPToolset → result injected back into context → repeat until final response. You never write this loop manually."**

In Module 3, we wrote the tool-calling logic ourselves in the buyer and seller agent files. In Module 4, ADK handles that entire loop. Our code just defines the agent and calls `runner.run_async()`.

---

### SLIDE 62 — ADK Agent Lifecycle: Construction → Entry → Execution → Exit
**[~4 min]**

`[SHOW CODE: buyer_adk.py structure]`

The ADK agent has four phases:

**Phase 1: Construction (`__init__`)** — store config only. No side effects. No subprocesses. This is just recording what we want to create.

**Phase 2: Entry (`__aenter__`)** — spawn MCP subprocesses. Discover tools via `list_tools()`. Build LlmAgent + Runner. Now the agent is ready to take turns. This runs every time you use the agent as a context manager.

**Phase 3: Execution (`_run_agent()`)** — GPT-4o selects tools. Runner calls MCPToolset automatically. Result injected back into context. Repeat until final response.

**Phase 4: Exit (`__aexit__`)** — close MCP connections. Terminate subprocesses. No leaked processes.

```python
async with BuyerAgentADK(session_id='abc123') as buyer:
    result = await buyer.make_initial_offer_envelope()
# MCP subprocesses cleaned up here automatically
```

The `async with` pattern ensures Phase 4 always runs, even if Phase 3 throws an exception.

---

### SLIDE 63 — runner.run_async(): The ADK Event Loop
**[~4 min]**

`[SHOW CODE: buyer_adk.py, the _run_agent method]`

```python
async def _run_agent(self, prompt: str) -> str:
    from google.genai.types import Content, Part

    content = Content(parts=[Part(text=prompt)])

    final_response = ''
    async for event in self._runner.run_async(
        user_id=self._user_id,
        session_id=self._session_id,
        new_message=content,
    ):
        # Optional: log tool calls for educational output
        if hasattr(event, 'tool_calls') and event.tool_calls:
            for tc in event.tool_calls:
                print(f'  Calling tool: {tc.function.name}')

        # Capture the final response (last event with is_final_response)
        if event.is_final_response() and event.content:
            for part in event.content.parts:
                if hasattr(part, 'text') and part.text:
                    final_response += part.text

    return final_response
```

`run_async()` returns an async generator of events. Events include: tool call requests, tool results, partial text, and the final response.

This is the event loop that ADK handles for you. Without ADK, you'd write: "call GPT-4o, check if it wants to call a tool, call the tool, inject result, call GPT-4o again, repeat until done." With ADK's `run_async()`, you just iterate over events.

The `InMemorySessionService` is why each call to `run_async()` has the full conversation history — it loads history from the session store, adds the new turn, runs the LLM, and saves back.

---

### SLIDE 64 — InMemorySessionService: Conversation State
**[~3 min]**

`[SHOW CODE: the session service setup in buyer_adk.py]`

```python
# In __aenter__:
self._session_service = InMemorySessionService()
self._runner = Runner(
    agent=self._agent,
    app_name=APP_NAME,
    session_service=self._session_service,
)
await self._session_service.create_session(
    app_name=APP_NAME,
    user_id=self._user_id,
    session_id=self._session_id,
    state={'round': 0, 'status': 'negotiating'},
)
```

The `InMemorySessionService` maintains conversation history per `session_id`. Every `run_async()` call automatically loads the previous turns and adds the new one.

This is why agents in Module 4 have "memory" across turns — the seller remembers what it countered in Round 1 when it's responding in Round 2. Not because we manually pass history, but because ADK's session service stores and retrieves it.

In production, you'd swap `InMemorySessionService` for a database-backed session service — the interface is the same. That's ADK's provider pattern in action.

---

### SLIDE 65 — What Is A2A Protocol?
**[~4 min]**

Now we add the final piece: A2A — the Agent-to-Agent protocol.

A2A is an **open standard from Google (2025)** for agents to communicate over HTTP. Six key concepts:

1. **Each agent exposes an Agent Card** at `GET /.well-known/agent-card.json` — a JSON document describing what the agent can do, its skills, its transport, and its endpoint URL.

2. **Messages are sent via JSON-RPC** — `POST /` with `method: "message/send"` and the message in the body.

3. **Responses are structured Task objects** with a lifecycle: `submitted → working → completed` (or `failed`).

4. **Transport: JSONRPC over HTTP** — no WebSockets needed for basic use.

**Why A2A?**

- **Agents can be in separate processes** — buyer and seller are truly independent
- **Language-agnostic** — HTTP protocol means the seller could be written in TypeScript, Go, Java — doesn't matter
- **Discoverable via Agent Card** — buyer doesn't import seller code; it fetches the Agent Card and knows what to send
- **Standard task lifecycle** — structured state management across the network boundary

In Module 3, the buyer called `seller_agent.respond_to_offer_envelope()` — a direct Python method call. In Module 4, it sends an HTTP POST to `http://127.0.0.1:9102` with a JSON-RPC payload. The network boundary is real.

---

### SLIDE 66 — A2A and MCP
**[~2 min]**

This diagram shows how MCP and A2A relate to each other — they solve different problems.

**MCP** is vertical — within an agent. Each agent uses MCP to talk to its own tools. Buyer → pricing server. Seller → pricing server + inventory server.

**A2A** is horizontal — between agents. Buyer ↔ Seller over HTTP.

An agent might use both simultaneously: A2A to coordinate with other agents, and MCP to access its own tools. They're complementary protocols, not competing ones.

In our system: Buyer and Seller use A2A to exchange offers over HTTP. Internally, each uses MCP (via ADK's MCPToolset) to access pricing and inventory data.

---

### SLIDE 67 — Agent Card: Discovery Metadata
**[~3 min]**

`[SHOW CODE: a2a_protocol_seller_server.py, the _build_agent_card function]`

```python
from a2a.types import AgentCard, AgentCapabilities, AgentProvider, AgentSkill

def _build_agent_card(base_url: str) -> AgentCard:
    return AgentCard(
        name='adk_seller_a2a_server',
        description='ADK-backed seller agent exposed via A2A protocol',
        url=base_url,               # e.g. http://127.0.0.1:9102
        version='1.0.0',
        protocolVersion='0.3.0',
        preferredTransport='JSONRPC',
        capabilities=AgentCapabilities(streaming=False, pushNotifications=False),
        skills=[
            AgentSkill(
                id='real_estate_seller_negotiation',
                name='Real Estate Seller Negotiation',
                description='Responds to buyer offers with counter-offers',
                tags=['real_estate', 'negotiation', 'seller', 'a2a'],
            )
        ],
        provider=AgentProvider(
            organization='Negotiation Workshop',
            url='https://example.local/negotiation-workshop',
        ),
    )
```

This is the agent's business card. When the buyer hits `GET /.well-known/agent-card.json`, it gets back this JSON. It knows:
- The agent's name and description
- The endpoint URL
- The protocol version
- What skills the agent has
- How to contact it

The buyer agent uses `A2ACardResolver` to fetch this card. From that card, it knows everything it needs to send a message. No hardcoding, no imports.

---

### SLIDE 68 — SellerADKA2AExecutor: Handling Requests
**[~4 min]**

`[SHOW CODE: the SellerADKA2AExecutor class]`

```python
class SellerADKA2AExecutor(AgentExecutor):
    async def execute(self, context: RequestContext,
                      event_queue: EventQueue) -> None:
        # TaskUpdater emits task lifecycle events to A2A client
        updater = TaskUpdater(event_queue,
                              task_id=context.task_id,
                              context_id=context.context_id)
        await updater.start_work()

        incoming_text = context.get_user_input().strip()
        try:
            parsed = BuyerEnvelope.model_validate(
                json.loads(incoming_text)
            )

            seller = await SESSION_REGISTRY.get_or_create(parsed.session_id)
            response = await seller.respond_to_offer_envelope(parsed)
            response_json = response.model_dump(mode='json')

            msg = updater.new_agent_message(
                parts=[TextPart(text=json.dumps(response_json))]
            )
            await updater.complete(msg)

        except Exception as error:
            msg = updater.new_agent_message(
                parts=[TextPart(text=f'ERROR: {error}')]
            )
            await updater.failed(message=msg)
```

Three things here:

1. **`TaskUpdater`** — manages the A2A task lifecycle. `start_work()` transitions task to `working`. `complete()` transitions to `completed`. `failed()` transitions to `failed`. The buyer client can poll these states.

2. **`BuyerEnvelope.model_validate(json.loads(incoming_text))`** — strict JSON parsing with Pydantic. If the buyer sends malformed JSON, it fails immediately with a clear error. No silent failures.

3. **`SESSION_REGISTRY.get_or_create(parsed.session_id)`** — gives us the same `SellerAgentADK` instance for a given session. Multi-turn continuity — the seller in Round 2 is the same object as Round 1, with its ADK session history intact.

---

### SLIDE 69 — A2A FastAPI Server Startup
**[~3 min]**

`[SHOW CODE: the main() function in a2a_protocol_seller_server.py]`

```python
async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', default=9102)
    args = parser.parse_args()

    base_url = f'http://{args.host}:{args.port}'
    card = _build_agent_card(base_url)

    handler = DefaultRequestHandler(
        agent_executor=SellerADKA2AExecutor(),
        task_store=InMemoryTaskStore(),
        queue_manager=InMemoryQueueManager(),
    )

    app_builder = A2AFastAPIApplication(
        agent_card=card,
        http_handler=handler
    )
    app = app_builder.build(
        agent_card_url='/.well-known/agent-card.json',
        rpc_url='/'
    )

    import uvicorn
    config = uvicorn.Config(app=app, host=args.host, port=args.port)
    server = uvicorn.Server(config)
    try:
        await server.serve()
    finally:
        await SESSION_REGISTRY.close_all()  # graceful shutdown
```

`A2AFastAPIApplication.build()` creates two routes:
- `GET /.well-known/agent-card.json` — returns the agent card
- `POST /` — handles A2A JSON-RPC `message/send` requests

`uvicorn` serves it as a standard async HTTP server. The buyer hits port 9102 over HTTP.

The `finally: await SESSION_REGISTRY.close_all()` is the graceful shutdown — when you Ctrl+C the server, it cleanly shuts down all active seller ADK agents and their MCP subprocesses.

---

### SLIDE 70 — SellerSessionRegistry: Multi-Turn Continuity
**[~3 min]**

`[SHOW CODE: the SellerSessionRegistry class]`

```python
class SellerSessionRegistry:
    """Reuses one SellerAgentADK per session_id for multi-turn continuity."""

    def __init__(self):
        self._agents: dict[str, SellerAgentADK] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(self, session_id: str) -> SellerAgentADK:
        async with self._lock:
            existing = self._agents.get(session_id)
            if existing is not None:
                return existing

            agent = SellerAgentADK(session_id=f'seller_{session_id}')
            await agent.__aenter__()   # starts MCP subprocesses
            self._agents[session_id] = agent
            return agent

    async def close_all(self):
        async with self._lock:
            agents = list(self._agents.values())
            self._agents.clear()
        for agent in agents:
            await agent.__aexit__(None, None, None)

SESSION_REGISTRY = SellerSessionRegistry()   # module-level singleton
```

Why is this important? Without the registry, every HTTP request to the seller creates a new `SellerAgentADK` — which means a new MCP session, no conversation history, no memory of previous rounds.

With the registry: the first request for `session_id='abc123'` creates a new agent. The second request for the same session_id returns the **same agent object** — with its `InMemorySessionService` intact. The seller in Round 2 remembers Round 1.

The `asyncio.Lock()` prevents race conditions if two requests arrive simultaneously for the same session_id.

---

### SLIDE 71 — A2A Call Flow End-to-End
**[~5 min]**

This is the complete picture. Let me trace through one full round.

**Step 1: BUYER ADK OFFER.** `BuyerAgentADK.make_initial_offer()`. Calls MCP pricing server. Calls GPT-4o. Produces `price: $438,000`.

**Step 2: DISCOVER SELLER.** `A2ACardResolver(base_url=seller_url).get_agent_card()`. Issues `GET http://127.0.0.1:9102/.well-known/agent-card.json`. Gets back the agent card with endpoint and capabilities.

**Step 3: SEND OFFER.** `A2AClient(agent_card=card).send_message(offer_envelope)`. Issues `POST http://127.0.0.1:9102` with JSON-RPC payload `{'method': 'message/send', 'params': {'buyer offer: $438,000'}}`.

**-- NETWORK BOUNDARY --** Port 9102. No shared memory. No shared imports.

**Step 4: EXECUTOR RECEIVES.** `SellerADKA2AExecutor.execute()`. `TaskUpdater.start_work()`. Parses the offer JSON. Gets seller agent from SESSION_REGISTRY.

**Step 5: SELLER ADK RUNS.** `SellerAgentADK.respond_to_offer_envelope()`. Calls MCP pricing + inventory. Calls GPT-4o. Produces `COUNTER_OFFER: $465,000`.

**Step 6: RESPONSE RETURNED.** `TaskUpdater.complete(counter_offer_json)`. HTTP response sent back to orchestrator. Task status: `completed`.

The orchestrator then parses the counter-offer, gives it to the buyer for Round 2, and repeats.

This is a real distributed system. Two processes. One network boundary. Standard protocol.

---

### SLIDE 72 — Live Zoom Poll
**[~3 min]**

Before we run the final demo, let's do a quick pulse check.

`[LAUNCH ZOOM POLL]`

Take 2 minutes to fill out the poll. This helps me understand where everyone is and what to spend extra time on.

`[WAIT FOR RESULTS]`

`[COMMENT ON RESULTS: "I can see most people are following the MCP concept well. A2A is newer so if that needs more time, we can come back to it in Q&A."]`

---

### SLIDE 73 — [DEMO 4] Module 4 Implementation Notes: Google ADK Overview
**[~5 min]**

Let's run the ADK buyer agent first, without the A2A server.

`[DEMO: Switch to terminal]`

```bash
# Run just the buyer ADK agent to see it call MCP tools
python m4_adk_multiagents/buyer_adk.py
```

`[SHOW OUTPUT: Tool calls being logged — "Calling tool: get_market_price", then GPT-4o reasoning, then offer]`

See the tool calls being logged? That's the ADK event loop in action. GPT-4o decided to call `get_market_price()` before making its offer. ADK executed that call via MCPToolset. The result came back. GPT-4o used it to decide on `$438,000`.

We didn't write any of that loop. ADK's `Runner.run_async()` handled it.

Now let's run the full ADK seller against a real buyer offer:

```bash
python m4_adk_multiagents/seller_adk.py
```

`[SHOW: Seller calling BOTH pricing and inventory MCP tools]`

Notice the seller calls `get_minimum_acceptable_price()` — getting its floor price. The buyer never called that. Information asymmetry working correctly.

---

### SLIDE 74 — [DEMO 5] Module 4 Implementation Notes: A2A Protocols
**[~8 min]**

Now the big one — the full A2A negotiation across HTTP.

`[DEMO: Two terminals]`

Terminal 1 — Start the seller as an HTTP service:
```bash
python m4_adk_multiagents/a2a_protocol_seller_server.py --port 9102
```

`[SHOW: Server starting on port 9102]`

Notice: this is a real HTTP server. It's serving `/.well-known/agent-card.json` and handling POST requests. It's ready to talk to any client over HTTP.

Terminal 2 — Run the full orchestrator:
```bash
python m4_adk_multiagents/a2a_protocol_http_orchestrator.py --seller-url http://127.0.0.1:9102 --rounds 5
```

`[SHOW OUTPUT: Round-by-round negotiation over HTTP]`

Watch this carefully. You'll see:
- Round 1: Buyer offers → HTTP POST → Seller counters
- Round 2: Buyer increases → HTTP POST → Seller decreases
- Rounds continue until agreement

`[POINT OUT: "Every round is a separate HTTP request. The buyer doesn't share memory with the seller. The seller remembers previous rounds via SESSION_REGISTRY + ADK session history."]`

`[IF DEAL REACHED: "See that? Deal reached at ~$449K. Right in the zone of agreement between $445K and $460K. The system works exactly as designed."]`

Now try the single-turn demo:
```bash
python m4_adk_multiagents/a2a_protocol_buyer_client_demo.py --seller-url http://127.0.0.1:9102
```

`[SHOW: Discovery of agent card, then single message/response]`

This shows the three steps: discover (GET agent card), then send (POST message/send), then parse response. In two minutes, you have a client that can talk to any A2A-compliant agent.

---

### SLIDE 75 — Module 4 Recap: ADK Intelligence Behind A2A Protocol Boundary
**[~3 min]**

This is your Module 4 summary.

**Buyer ADK** (top left) — `buyer_adk.py` + `InMemorySessionService`. Calls MCP pricing only. Calls GPT-4o → offer decision. Sends over A2A boundary.

**A2A Protocol Boundary** — `GET /.well-known/agent-card.json`. `POST /message/send` JSON-RPC. No shared memory. No shared imports. HTTP on port 9102.

**Orchestrator** (`a2a_protocol_http_orchestrator.py`) — up to 5 rounds per negotiation. Tracks state per round. Parses counter-offer. Loops.

**Seller Server** (`a2a_protocol_seller_server.py`) — FastAPI + A2A SDK. `SellerADKA2AExecutor` handles requests. Task lifecycle: submitted → working → completed.

**Seller ADK** (`seller_adk.py`) — `LlmAgent` + Runner. 4 MCP tools: 2 pricing + 2 inventory. Calls `get_minimum_acceptable_price()` → floor price. Counter decision.

**Terminal Outcomes** — AGREED (deal reached), DEADLOCKED (task failed), BUYER_WALKED (structured error, no crashes, state preserved).

This is the complete picture of a production multi-agent system.

---

## FINAL SUMMARY
### *Slides 76–80 | Target: 15 minutes | 3:50–4:00*

---

### SLIDE 76 — Complete Architecture: All Four Layers Together
**[~5 min]**

This is it. The complete architecture, all four layers together.

**M1: Termination** — `state_machine.py`. FSM with terminal states. Max 5 rounds enforced. Termination is a mathematical guarantee.

**M2: Real Data** — MCP. `FastMCP + @mcp.tool()`. `inventory_server.py` is seller only. `pricing_server.py` is both agents.

**M3: Orchestration** — LangGraph + StateGraph. Both agents in one process. `NegotiationState` TypedDict. Full audit trail via `Annotated[list, operator.add]`.

**M4: Network Decoupling** — A2A Protocol + Google ADK. `A2AClient` → JSON-RPC. `A2AFastAPIApplication` serves the seller. Each agent in its own process.

**Outcomes** — AGREED, DEADLOCKED, BUYER_WALKED. Deterministic. Observable. Bounded.

Every single one of the 10 failure modes from Module 1 is now fixed. Let me do a quick sweep:

1. Raw string messages → NegotiationMessage TypedDict
2. No schema validation → Pydantic `model_validate()` at A2A boundary
3. While True loop → LangGraph StateGraph with conditional edges to END
4. No turn limits → `MAX_ROUNDS = 5`, route to END when exceeded
5. Fragile regex → `price: float` field in TypedDict, no regex needed
6. No termination guarantee → FSM terminal states + LangGraph END node
7. Silent failures → strict `json.loads()` + Pydantic, fail-fast
8. Hardcoded prices → `get_market_price()` via MCP on every turn
9. No observability → full history via `Annotated[list, operator.add]`
10. No evaluation → structured outcomes with agreed price, failure reason

Ten failures. Four modules. All fixed.

---

### SLIDE 77 — Q&A
**[~5 min]**

`[ASK CLASS:]`
- "What questions do you have on the A2A protocol?"
- "Is the relationship between MCP (vertical, agent↔tools) and A2A (horizontal, agent↔agent) clear?"
- "Any questions on how ADK's MCPToolset connects to our custom MCP servers?"
- "Any questions you've been holding throughout the class?"

`[TAKE 4-5 QUESTIONS]`

I want to remind you: if you're wondering about something implementation-specific — "how do I handle auth in MCP?" or "how do I persist sessions to a database?" — post it in Discord. Those are great questions for the technical coaching session on Wednesday.

---

### SLIDE 78 — The Build Is Complete — Push to GitHub
**[~2 min]**

One final thing before we close.

You've just built a production-grade multi-agent system. Two AI agents, MCP tool access, LangGraph orchestration, A2A over HTTP. This is genuinely non-trivial work.

**Package it. Put it on GitHub. Make it a portfolio piece.**

The README template linked on this slide will help you describe what you built in a way that's clear to a hiring manager or a technical interviewer.

When someone asks you in an interview: "Have you built any agentic AI systems?" — you will have a concrete answer, with a working GitHub link, demonstrating:
- Multi-agent coordination
- MCP protocol integration
- LangGraph state management
- A2A networked agents
- Production patterns (termination, observability, strict validation)

That's a strong portfolio piece. Use it.

---

### SLIDE 79 — Key Patterns to Remember
**[~3 min]**

Six patterns to take into your next project. Commit these to memory.

**FSM for loops:** Empty successor sets prove termination — no `while True`. When you have any agent loop, define the states explicitly and identify the terminal ones.

**`@mcp.tool()`:** Type hints become JSON schema — one decorator, discoverable. Every time you want an agent to access external data, write an MCP server.

**Annotated reducer:** `Annotated[list, operator.add]` prevents history overwrite. Use this whenever you need an append-only log in LangGraph state.

**async context manager:** `MCPToolset` subprocesses need `__aexit__` for cleanup. Any resource that spawns subprocesses or opens connections belongs in an async context manager.

**AgentCard:** `/.well-known/agent-card.json` is the discoverable agent contract. When building services that agents can talk to, always provide an Agent Card.

**Info asymmetry:** MCP access lists are the mechanism — not prompt text. Don't use "you don't know the seller's floor" in the buyer's system prompt. Use separate MCP servers with access control.

These six patterns generalize far beyond real estate negotiation. They apply to any multi-agent system you'll build.

---

### SLIDE 80 — Thank You
**[~1 min]**

Thank you all for four hours of focused work. You've covered a lot of ground today.

Quick recap of what you built:
- Module 1: FSM that guarantees negotiation termination
- Module 2: Two MCP servers with information asymmetry
- Module 3: Full LangGraph multi-agent workflow
- Module 4: A2A-over-HTTP with Google ADK

**Your homework for the week:**
1. Complete the MCQ and coding assignment on Uplevel
2. Run the full Module 4 demo on your own machine
3. Attempt at least one exercise from each module
4. If you want a challenge: try the Module 3 capstone — build an inspector agent that analyzes the negotiation transcript and tells you who got the better deal

**Technical coaching session is Wednesday** — bring your assignment questions.

See you next week.

---

## APPENDIX: DEMO SCRIPTS

### Demo 1 — Module 1 (Slides 27)
```bash
cd c:\Repos\real-estate-negotiation-simulator

# Show the naive version
python m1_baseline/naive_negotiation.py

# Show the FSM version
python m1_baseline/state_machine.py

# Key things to point out:
# 1. Naive: raw string output, potentially None prices, no clear termination
# 2. FSM: explicit state transitions logged, terminates cleanly at max_rounds
```

### Demo 2 — Module 2 (Slide 40)
```bash
# Terminal 1: GitHub MCP demo
python m2_mcp/github_agent_client.py

# Terminal 1 (after): SSE pricing server
python m2_mcp/pricing_server.py --transport sse --port 8000

# Terminal 2: SSE agent client
python m2_mcp/sse_agent_client.py

# Key things to point out:
# 1. Tool discovery: agent doesn't know tools at startup
# 2. Real market data returned (not hardcoded)
# 3. Structured JSON response, not raw text
```

### Demo 3 — Module 3 (Slide 56)
```bash
python m3_langgraph_multiagents/main_langgraph_multiagent.py

# Key things to point out:
# 1. Each round's offer and counter logged
# 2. MCP tool calls visible
# 3. Final state['history'] shows complete audit trail
# 4. Clean termination with status: 'agreed' or 'failed'
```

### Demo 4 — Module 4 ADK (Slide 73)
```bash
# Show buyer ADK calling MCP tools
python m4_adk_multiagents/buyer_adk.py

# Show seller ADK calling both servers
python m4_adk_multiagents/seller_adk.py
```

### Demo 5 — Module 4 A2A Full (Slide 74)
```bash
# Terminal 1: Start seller as HTTP service
python m4_adk_multiagents/a2a_protocol_seller_server.py --port 9102

# Terminal 2: Full orchestrator
python m4_adk_multiagents/a2a_protocol_http_orchestrator.py \
    --seller-url http://127.0.0.1:9102 --rounds 5

# Terminal 2 (optional): Single-turn demo
python m4_adk_multiagents/a2a_protocol_buyer_client_demo.py \
    --seller-url http://127.0.0.1:9102

# Key things to point out:
# 1. Two separate processes communicating over HTTP
# 2. Agent card discovery
# 3. Task lifecycle: submitted → working → completed
# 4. SESSION_REGISTRY maintains seller memory across rounds
```

---

## TIMING GUIDE

| Section | Slides | Target | Cumulative |
|---------|--------|--------|------------|
| Opening & Housekeeping | 1–10 | 20 min | 0:20 |
| What Are We Building? | 11–15 | 15 min | 0:35 |
| Module 1: Baseline + Demo | 16–29 | 40 min | 1:15 |
| Module 2: MCP + Demo | 30–42 | 35 min | 1:50 |
| Break (10 min) | 43 | 10 min | 2:00 |
| Post-break Q&A + Transition | 44–45 | 5 min | 2:05 |
| Module 3: LangGraph + Demo | 46–57 | 40 min | 2:45 |
| Q&A + Break (5 min) | 58–59 | 10 min | 2:55 |
| Module 4: ADK + A2A + Demos | 60–75 | 55 min | 3:50 |
| Wrap-up + Patterns + Goodbye | 76–80 | 10 min | 4:00 |

**If running ahead:** Spend extra time on live Q&A, go deeper into exercises.

**If running behind:** Condense housekeeping slides 3–8 (2 min combined), skip Demo 4 (ADK only), focus on Demo 5 (A2A full), trim Module 2 slides 37–38.
