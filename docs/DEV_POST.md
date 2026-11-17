---
title: "We closed a street and Timișoara got faster: a traffic stress tester for the whole city"
published: false
tags: mlhacks, python, react, opensource
---

## You may think Timișoara has good traffic.

Then it's **8 in the morning**. Or **5 in the afternoon**. Calea Martirilor isn't moving, Waze sends you down a side
street you've never seen, and that street is full too.

So what's the usual answer? ***More roads. More lanes. More space for cars.***

> ### What if I told you that closing a street, or taking a lane away from cars, can make traffic *lighter*?

It sounds backwards. It's a real effect, proven in traffic science for over 50 years: **Braess's paradox**. And we
built the first tool that finds where it happens in Timișoara.

---

## 🚦 Meet Paradox: a Braess-paradox stress tester for Timișoara, built for Primăria Timișoara.

Before the city spends a single leu, it can test an idea on the real streets:

- 🚧 **Close a street**, and see where every car goes.
- 🚌 **Give a lane to buses, bikes or a wider sidewalk**, and see what it really costs drivers, **in seconds**.
- 🛠️ **Planning road works?** Close the street in Paradox first, and see which side streets fill up and which
  intersections suffer.

No waiting weeks for a study just to learn whether an idea is worth studying. The city can argue with **numbers
instead of opinions** about where the next bike or bus lane should go, and design transport that works for
**everyone**: people in cars and people who aren't.

### 🧲 How does it know? Every zone of the city is a magnet.

- 🏠 **Homes push cars out.** From every building (its size, its floors, its type) we estimate how many people live
  there and how many car trips they make at rush hour.
- 🏫 **Destinations pull cars in.** Schools, offices, shops and clinics each attract trips. The bigger the pull and the
  closer the destination, the more cars head there.
- 🚗 **Every driver is selfish.** That's human: each one takes the route that's fastest for them, exactly as Waze tells
  them. We compute the moment nobody can get there faster by switching. That's the **Wardrop equilibrium**, solved
  with a classic graph algorithm, **Frank-Wolfe**, in a tenth of a second.

### ⚡ And here's the paradox.

When everyone takes the same shortcut, it floods the intersection it leads into and slows down everyone else.
**Remove the shortcut, and the intersection breathes again.**

> In our model, closing **Piața Tineretului** at rush hour gets drivers on Calea Martirilor home **13 seconds sooner**.
> At midday it doesn't help, so the tool tells the city when *not* to do it, too.

### 🚌 And it nudges people toward public transport.

For every bus lane, Paradox shows **how many drivers would need to switch to the bus for it to cost nothing**. Next to
it is what real people in Timișoara told us in our survey, so the city can see **a greener street can still be a fast
street**.

**Built on real data:** the full street map from **OpenStreetMap**, **Primăria Timișoara's open APIs** for STPT lines,
timetables, tickets and Timpark parking, the city's mobility plan, and a survey of **31 Timișoara residents**.

> ## Paradox: test it before you build it. 🚦

---

<!-- 🎬 Put a 10-second GIF here: click "Piața Tineretului" → the map turns blue/orange → "−13 s" appears -->

## Under the hood

We started where the stakes are high: the **Calea Martirilor / Strada Cluj corridor**, one of the city's main arteries,
with 9,500 cars an hour at the morning rush. Because the whole engine is built straight from **OpenStreetMap** and the
**city's own open data**, pointing it at any other neighbourhood of Timișoara is a configuration change, not a rewrite.

- **The real street network** from OpenStreetMap: 385 street segments, 30 traffic lights, lanes, speed limits, 39 turn
  bans.
- **Then we try everything**: close every busy street segment, take a lane from every multi-lane street, re-solve the
  whole city each time. About 300 scenarios per hour of the day, in ~10 seconds.

The time on each street follows the classic BPR curve:

```
time = free time × (1 + 0.15 × (cars ÷ capacity)⁴)
```

Quiet streets barely slow down; full ones slow down fast. That steep curve is exactly what lets a shortcut hurt
everyone. Our solver reproduces the textbook Braess example exactly (**65 minutes without the shortcut, 80 with it**),
and that's one of our 47 automated tests.

Our approach follows Burov et al., *Detecting Braess Routes* (UC Berkeley, IEEE ITSC 2021). They found the paradox
disappears when traffic is light. **So did we**: no Braess street at midday, several at rush hour.

## We asked real people

We ran a survey with 31 people in Timișoara:

- **68%** think closing a side street makes traffic worse (0% think it helps)
- **96%** of drivers follow the shortcuts their navigation app suggests
- **50%** go around the main roads through side streets, and one of the streets they named, **Strada Cozia**, is one
  of the Braess streets our app found

The answers feed back into the app: they check our assumptions (car share, people per car) against the city's mobility
plan.

## Built with

- **OpenStreetMap** (Overpass) for streets, lanes, lights, buildings and points of interest
- **Timișoara City Hall open APIs**: STPT lines and live timetables, ticket prices, Timpark parking zones
- **Python, FastAPI, NumPy, SciPy** for the traffic model
- **React, TypeScript, Vite, Tailwind, MapLibre GL** with OpenFreeMap tiles for the map

## What broke at 3am 🔥

- **Our app counted bus lanes as car lanes.** OpenStreetMap includes bus lanes in `lanes=4`. Strada Cluj looked like it
  had a phantom fourth car lane, so taking a lane away "did nothing". One line of tag parsing later, it finally reacted.
- **Real turn restrictions disconnected the city.** Importing every "no left turn" from OSM made 38 trips impossible.
  We now add each restriction only if every neighbourhood can still reach every other.
- **Two UIs, one weekend.** One teammate rebuilt the whole design while another rewired the backend. We merged at 2am
  and again at 3am, and somewhere in there a stuck vim swap file guarded the merge like a boss fight.
- **A street that "never changed".** We spent a while hunting a bug where removing a lane gave 0.00%. It wasn't a bug:
  it was a 25-metre stub at the edge of the map, 12% full. Not every street matters, and the app is honest about it.

## What we're proud of

- It runs on **real streets and real city data**, not a toy network
- Every number shows **where it comes from**, and the app says plainly that traffic is *estimated* until someone counts
  it
- It's fast enough to use live in a meeting
- It's **open source (MIT)**, so any city can run it

## What's next

- **One morning of traffic counts** at the 16 entry points turns "estimated" into "calibrated"
- Queues at traffic lights that grow with traffic, so bus lanes show their real benefit
- Trams and cycling demand
- **Every neighbourhood of Timișoara**, one corridor at a time, from the same OpenStreetMap pipeline
- A pilot with City Hall on their next real lane project: test it here first, then build it

## Try it / read the code

👉 **[github.com/lucasbora/Parad0x](https://github.com/lucasbora/Parad0x)**

Built at **UniHack** by Lucas, Rareș, Laura and Adriana. If you work on streets, buses or bikes in your city, we'd love
to hear from you in the comments. 🚦
