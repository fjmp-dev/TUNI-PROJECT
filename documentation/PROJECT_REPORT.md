**MIR SUITE**

Project Report

Dual-arm mobile manipulation platform\
MiR200 · 2x UR5e · BrainCo Revo1 · Orbbec Gemini · Nordbo\
Tampere University (TUNI) / Fastlab

Prepared for Prof. Lastra --- Version 1.0, July 2026

# 1. Introduction

This report summarizes the work carried out over the past two months on the robotic platform in the Fastlab: a mobile base (the MiR200) carrying two robotic arms (UR5e), a pair of robotic hands, a camera, and force sensors. It explains, in plain terms, the state the system was in when we started, the problems we ran into and solved along the way, where things stand now, and what it means in practice for anyone who wants to use the robot going forward.

# 2. The Situation When We Started

The robot was already able to move and had been programmed by a previous lab member, Eemil. However, everything about it was fragile and hard to use:

- **Everything ran by hand.** Operating the robot meant connecting to its onboard computer over a remote terminal and manually typing the right commands, in the right order, in the right terminal window — something only the original author really knew how to do reliably.
- **The mobile base was overloading the system.** The mobile base (MiR200) was constantly sending a huge amount of internal status information into the same communication channel the arms used to talk to each other. This was the equivalent of two people trying to have a conversation while a hundred other voices talked over them at the same time. The result was that the mobile base itself would trip its own safety system and shut down (an "Error 9000"), and the arms would occasionally miss or delay commands.
- **There was no safety net.** All the software ran with full, unrestricted access to the onboard computer, there was no password protection worth mentioning, and there was no way to see what the robot was doing without being an expert in the underlying tools.
- **There was no way to see or control the robot remotely.** No screen, no dashboard, nothing — just a command line.

In short: a robot that worked, but that only one person could safely operate, and where two of its own major parts (the mobile base and the arms) were quietly interfering with each other.

# 3. What We Worked On

## 3.1 Making the Software Modular and Safe

We reorganized all of the robot's software into clearly separated, self-contained pieces — one for each physical part of the robot (the arms, the mobile base, the camera, the hands) — using a technology called Docker, which packages each piece of software so it runs the same way every time and cannot accidentally interfere with the others. Alongside this, we removed the unrestricted, "do-anything" access every one of these pieces used to have, and gave each one only the narrow permissions it actually needs to do its job.

## 3.2 Stopping the Mobile Base from Overloading the System

We found and adopted a better way (already designed by another team member, Wael, for a related project) to connect the mobile base to the rest of the robot: instead of forwarding *everything* the mobile base says, it now forwards only the handful of things that are actually needed (its position, its safety-laser readings, its battery level). The flood of internal chatter dropped by roughly 95%, and the mobile base's self-triggered emergency stop (the "Error 9000" issue) has not happened again since. We also added an automatic watchdog that notices if this connection ever freezes and restarts it by itself, without anyone needing to notice or intervene.

## 3.3 Building an Actual Control Panel

Before this work, there was no interface at all — just a command line. We built a proper web-based control panel: log in from a browser, see the robot's live status, watch the camera feed, move the arms, check the mobile base's position and battery, and start or stop different parts of the system, all from one screen. It also supports multiple user accounts with different permission levels, and every connection is encrypted, so information travelling between a laptop and the robot cannot be read by anyone else on the network. Default passwords were replaced with strong ones, and remote access to the underlying computer terminal (previously wide open) is now locked down and requires a separate password of its own.

## 3.4 Making the Arms Trustworthy

For a while, the arms had a subtle and frustrating problem: the control panel would say a movement succeeded, but the arm would not actually move. We traced this to the robot's own safety system quietly stopping the arm's control program in the background (triggered by a speed-limit setting on the robot that is currently set too conservatively) without clearly reporting it. We fixed the software so it now double-checks that the arm actually moved before reporting success, and automatically restarts the arm's control program when needed. We also added a small on-screen 3D model of both arms so their position can be checked at a glance, and a safety rule that prevents a person from hand-guiding an arm until the robot has confirmed it is actually holding something (over 1 kg), so the arm cannot be moved by hand unexpectedly.

## 3.5 Fixing the Camera

The live video feed from the robot's camera was originally almost unusable — barely one or two frames per second, more of a slideshow than a video. We found this was caused by how the image data was being converted for the browser, not by the camera itself, and after adjusting the video settings we brought it up to a smooth ~30 frames per second.

## 3.6 Making It Easy for Anyone to Use

Most recently, we added a simple desktop icon: one click turns the whole system on (and opens the control panel automatically in the browser), another click turns it off. No commands to remember, no terminal required. Starting the arms themselves is still a separate, deliberate step taken from inside the control panel, so nothing moves just because someone turned the system on.

# 4. Problems We Ran Into and Solved

| Problem | What Was Really Going On | How We Fixed It |
|---|---|---|
| The mobile base kept shutting itself down with a safety error | It was flooding the shared communication channel with far more information than anyone needed | Switched to forwarding only the handful of essential pieces of information |
| The "safety watchdog" we built was itself restarting a perfectly healthy connection | It was checking for activity in the wrong place, so it always looked idle even when it wasn't | Rewrote it to check real, live data instead |
| Arm movements would silently fail — the control panel said "done" but nothing moved | The robot's safety system had quietly paused the arm's control program | Made the software verify the arm actually moved, and automatically resume the control program |
| Editing a configuration file on the computer sometimes had no effect on the running system | A quirk of how Docker keeps a running program's files separate from the ones on disk | Learned to apply the fix directly inside the running program instead |
| The live camera feed was extremely slow | The way video frames were encoded for the browser was overloading the onboard computer | Lowered the video resolution to a setting the camera fully supports at full speed |
| The mobile base kept losing its connection | A weak Wi-Fi signal on the network band it happened to be using | Diagnosed the exact cause and identified the fix (moving it to a different Wi-Fi band with better range); this has been fixed once already and needs to be reapplied after a recent network change |
| A recording tool filled the entire hard drive in a few hours | It was saving far more data, with no limit, than intended | Limited what and how long it records |
| Sensor data appeared to be "there" but was actually empty after restarting parts of the system | A leftover technical artifact from how the communication system shares memory between programs | Documented the cause and the simple cleanup step |
| The mobile base occasionally stopped itself, blaming an obstacle that wasn't really there | A real (if brief) interruption of its rear safety sensor, most likely a stray cable or a dirty sensor window | Diagnosed the pattern; a physical inspection is the remaining step |
| Weak, default, or shared passwords everywhere | The system was never set up with security in mind | Replaced every default password, encrypted how they're stored, and locked down remote terminal access |

# 5. Where the Project Stands Now

- The mobile base and the arms no longer interfere with each other, and the mobile base's self-triggered shutdowns have stopped.
- Every part of the system runs with only the access it actually needs, rather than full, unrestricted control of the computer.
- All communication with the robot is encrypted and requires a login.
- There is a real, working control panel: live status, camera view, arm control with a 3D preview, and system management, usable by multiple people with different permission levels.
- The camera streams smoothly in real time.
- Turning the whole system on or off takes one click.
- When something goes wrong, the system now says so clearly, instead of failing silently.
- The remaining issues are known, documented, and assigned — not unexplained flakiness.

# 6. How This Helped the Robot's Development

Put simply, the robot went from being a system only its original builder could safely run, to one that can reasonably be handed to someone else. The mobile base and the arms can now be used together without one breaking the other — which matters a great deal for a robot whose whole purpose is to move around *and* manipulate objects at the same time. Anyone in the lab can now check on the robot, move an arm, or watch the camera from a browser, without needing to know the technical internals or have terminal access. Problems that used to be invisible (a silently failed move, a frozen connection) now surface immediately and often resolve themselves. And because the basic security is now in place, the system is in a reasonable state to be demonstrated to visitors, or eventually made reachable from outside the lab — neither of which was realistic before.

# 7. Before vs. Now

**Before**, using the robot meant: connecting to its onboard computer through a remote terminal, knowing the exact technical commands and the order to run them in, hoping the mobile base wouldn't trip its own emergency stop, and having no way to see the camera or the robot's status without specialized tools — with no login, no encryption, and no record of who did what.

**Now**, using the robot means: clicking one icon on the desktop (or opening a single web address) to turn the system on, logging in with a personal account, and from a single screen: starting whichever part of the robot is needed, moving the arms and watching a 3D preview of their position, hand-guiding the robot safely, viewing the live camera and the mobile base's status, and — if a technical fix is ever needed — opening a built-in terminal instead of a separate remote connection. All of this now happens over an encrypted, logged-in connection, and the mobile base's internal chatter no longer floods the system the arms depend on.

# 8. Open Items

- **Arm speed-limit setting**: currently conservative enough that it occasionally pauses normal movements; needs to be adjusted directly on the robot (requires Wael).
- **Mobile base Wi-Fi**: currently on a weak signal; needs to be moved back to the better-performing network band (requires Wael / the network team).
- **Remote access from outside the lab**: technically possible but requires a small change to the cellular data plan plus the same security hardening applied everywhere else first; the plan is agreed, execution is pending.
- **Mobile base's internal clock**: off by about ten years (cosmetic — it only affects log timestamps).
- **Future phases**: the robotic hands' battery system and a motorized neck are documented but not yet integrated; a full self-navigation capability for the mobile base is planned as the next major phase.
