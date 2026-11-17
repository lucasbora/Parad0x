---
title: "More roads won't fix Timișoara's traffic. Sometimes fewer will."
published: false
tags: mlhacks, python, react, opensource
---

You may think Timișoara has good traffic.

Then it's **8 in the morning**. Or **5 in the afternoon**. Calea Martirilor is a parking lot, Waze sends you through a
side street you've never seen, and the side street is full too.

The usual answer is: *we need more roads. More lanes. More space for cars.*

**What if I told you that closing a street, or taking a lane away from cars, can make traffic lighter?**

It sounds wrong. It's a real, 50-year-old result in traffic science called **Braess's paradox**. And we built a tool
that finds exactly where it happens in Timișoara.

<!-- 🎬 GIF here: close Piața Tineretului → the map re-colours → "−13 s" on Calea Martirilor -->

## Meet Paradox

**Paradox is a Braess-paradox stress tester for Timișoara.** It's built for **Primăria Timișoara**: a place where the
city can test an idea *before* spending money on it.

- 🚌 **Where should the next bus lane go?** Give a lane to buses and see the cost for drivers, in seconds.
- 🚲 **A bike lane or a wider sidewalk?** Same street, same click, same honest answer.
- 🚧 **Road works next month?** Close the street in the app first and see where the traffic will go, which side streets
  will fill up, and which intersections will suffer.
- 🌳 **Can we take space from cars without making traffic worse?** Sometimes the answer is *yes, and traffic even gets
  better.*

No waiting weeks for a study just to find out whether an idea is worth studying. The planner, the bus operator and the
person at the council meeting can all look at the same map and argue with numbers instead of opinions. And it's
designed for **everyone on the street**: people in cars, on buses, on bikes and on foot.

## How it works: the city as a field of magnets

Think of every neighbourhood as a **magnet**.

**1. Homes push cars out.** We take every building in the area from OpenStreetMap: its footprint, its floors, its
type. A block of flats with 4 floors holds a lot more people than a house. From that we estimate **~24,500
residents**, and how many car trips they make each rush hour.

**2. Destinations pull cars in.** Schools, universities, offices, shops, clinics: each one has a "pull" depending on
its type and the time of day. At 8am schools and offices pull hardest. At 5pm everyone gets pulled back home.

**3. Closer magnets pull harder.** Like gravity, a destination 5 minutes away attracts far more trips than one 20
minutes away. Add the cars that only cross the area on their way somewhere else, and you have **9,500 cars an hour**
at the morning rush, each with an origin and a destination.

**4. Every driver is selfish.** And that's fine, that's human. Each driver takes the route that's fastest *for them*,
exactly like Waze tells them to. (In our survey, **96%** of drivers follow their navigation app's shortcuts.) We compute
the moment when nobody can get there faster by switching routes. That's the **Wardrop equilibrium**, and we solve it
with the **Frank-Wolfe algorithm** in about a tenth of a second.

**5. And here's the paradox.** When everyone grabs the same shortcut, the shortcut floods the intersection it leads
into, and that intersection slows down everyone else, including people who never touched the shortcut. Close the
shortcut, and the intersection breathes again. **Removing one street makes the whole area faster.**

The app does this for every street, automatically: it closes every busy segment one at a time, removes a lane from
every multi-lane street, and re-solves the whole network each time. About 300 "what ifs" per hour of the day, in
about ten seconds.

## What it found

> **Close Piața Tineretului at the morning rush, and drivers coming down Calea Martirilor arrive 13 seconds sooner.**
> About 450 cars an hour leave a residential square.

And then the twist that makes it useful: **at midday, the same closure doesn't help.** Traffic is lighter, the
shortcut isn't jammed, there's nothing to fix. So the recommendation isn't "close it forever", it's **close it at rush
hour**. A tool that tells you when *not* to do something is worth as much as one that tells you when to do it.

It also tells you when an idea is a disaster. Close Strada Arieș, and total time in traffic more than doubles. Better to
find that out in a browser than on a Monday morning.

## Nudging people toward the bus

Give a lane to buses and the app tells you **how many drivers would need to switch to the bus for that lane to cost
nothing**. On Calea Martirilor it's about **1 driver in 66**.

We also asked real people how much faster the bus would need to be before they'd leave the car, and that answer sits
right next to every bus-lane result. With the **"traffic evaporation"** option you can see what happens when, as real
cities have measured, part of the traffic simply finds another way once road space is reallocated.

It's not about forcing anyone out of their car. It's about showing, with numbers, that a greener street can still be a
fast street.

## We asked Timișoara

We surveyed **31 people** in Timișoara:

- **68%** said closing a side street makes traffic worse. Nobody said it could make it better.
- **96%** of drivers follow the shortcuts their navigation app suggests.
- Half of them go around the main roads through side streets, and one of the streets they named, **Strada Cozia**,
  is one of the streets our app flags.

Their answers aren't just a slide. They check the model's assumptions (how many trips are by car, how many people ride
in each car) against the city's mobility plan, and they appear next to the results in the app.

## Where the data comes from

- 🗺️ **OpenStreetMap**: every street, lane, speed limit, traffic light, turn ban, building and point of interest
- 🏛️ **Primăria Timișoara's open APIs**: STPT bus lines and live timetables, ticket prices, Timpark parking zones
- 📊 **PMUD Timișoara**, the city's mobility plan, for the share of trips made by car
- 🗣️ **Our own survey** of 31 people
- 📚 The science: Wardrop (1952), the BPR road-delay curve, and Burov et al., *Detecting Braess Routes*
  (UC Berkeley, IEEE ITSC 2021)

We started with one of the city's busiest corridors, **Calea Martirilor / Strada Cluj**. Because the whole engine is
built straight from OpenStreetMap and the city's open data, the next neighbourhood is a configuration change, not a
rewrite. And we're honest about what we don't know: the traffic is **estimated** from buildings until someone counts
it, and the app says so. One morning of traffic counts turns "estimated" into "calibrated".

## Built with

**Python · FastAPI · NumPy · SciPy** for the traffic engine, **React · TypeScript · Vite · Tailwind · MapLibre GL** with
OpenFreeMap for the map. 64 automated tests, including the textbook Braess example: 65 minutes without the shortcut,
80 with it, reproduced exactly.

## What broke at 3am 🔥

- **A phantom lane.** OpenStreetMap counts bus lanes inside the lane number, so Strada Cluj looked like it had an extra
  car lane, and taking a lane away "did nothing". One line of parsing later, it finally made sense.
- **Real turn bans cut the city in half.** Importing every "no left turn" made 38 trips impossible. Now each ban is only
  added if every neighbourhood can still reach every other.
- **The laptop ran out of memory.** The backend died several times over the weekend. Lesson learned: one terminal, zero Chrome
  tabs.
- **Two UIs, one weekend.** One of us rebuilt the design while another rewired the engine. Merge at 2am, merge again at
  3am, and a stuck vim swap file guarding the door like a final boss.
- **The street that never changed.** We hunted a "bug" where removing a lane gave 0.00%. It was a 25-metre stub at the
  edge of the map, 12% full. Not every street matters, and the app doesn't pretend otherwise.

## What's next

- **The rest of Timișoara**, one neighbourhood at a time
- **One morning of real traffic counts** to calibrate it
- Queues at traffic lights that grow with traffic, so bus lanes show their full benefit
- Trams and cycling demand
- **A pilot with Primăria Timișoara** on their next real lane project: test it in Paradox first, then build it

## Try it

👉 **[github.com/lucasbora/Parad0x](https://github.com/lucasbora/Parad0x)** (open source, MIT)

Built at **UniHack** by Lucas, Rareș, Laura and Adriana. If you plan streets, run buses, or just sit in traffic at 8am
and wonder why, we'd love to hear from you. 🚦
