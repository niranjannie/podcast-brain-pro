#!/usr/bin/env python3
"""Test script for audio generation optimizations."""

import time
import threading
import requests
import json
import os

BASE = "http://localhost:9876"

def health_poll(stop_event, label):
    """Poll /health every 2 seconds to verify server stays responsive."""
    ok_count = 0
    fail_count = 0
    while not stop_event.is_set():
        try:
            r = requests.get(f"{BASE}/health", timeout=5)
            if r.status_code == 200:
                ok_count += 1
            else:
                fail_count += 1
                print(f"  [{label}] Health FAIL: {r.status_code}")
        except Exception as e:
            fail_count += 1
            print(f"  [{label}] Health ERROR: {e}")
        time.sleep(2)
    print(f"  [{label}] Health polling done: {ok_count} OK, {fail_count} FAIL")


def test_longform(script, name, expected_chunks):
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"Words: {sum(len(item['content'].split()) for item in script)}")
    print(f"Expected chunks: {expected_chunks}")
    print(f"{'='*60}")

    payload = {
        "script": script,
        "cfg_scale": 1.3,
        "save_to_disk": True,
        "format": "interview",
        "language": "en"
    }

    stop_event = threading.Event()
    health_thread = threading.Thread(target=health_poll, args=(stop_event, name))
    health_thread.start()

    t0 = time.time()
    try:
        r = requests.post(f"{BASE}/tts/longform", json=payload, timeout=1200)
        elapsed = time.time() - t0
        stop_event.set()
        health_thread.join()

        if r.status_code == 200:
            chunks = r.headers.get("X-Chunks-Used", "?")
            gen_time = r.headers.get("X-Gen-Time-Sec", "?")
            print(f"  ✅ SUCCESS in {elapsed:.1f}s (server-reported gen: {gen_time}s, chunks: {chunks})")
            print(f"  Audio size: {len(r.content)} bytes")
            return True, elapsed
        else:
            print(f"  ❌ FAILED: {r.status_code} - {r.text[:200]}")
            return False, elapsed
    except Exception as e:
        elapsed = time.time() - t0
        stop_event.set()
        health_thread.join()
        print(f"  ❌ EXCEPTION: {e}")
        return False, elapsed


def main():
    print("Backend optimization test suite")
    print(f"Target: {BASE}")
    
    # Verify backend is up
    try:
        r = requests.get(f"{BASE}/health", timeout=5)
        print(f"Health: {r.json()}")
    except Exception as e:
        print(f"Backend not reachable: {e}")
        return

    # Test 1: Short single-pass (< 350 words)
    short_script = [
        {"role": "Host", "content": "Welcome to Tech Talks Today. I'm your host, Alex. Joining me is Dr. Sarah Chen, a leading researcher in artificial intelligence. Sarah, thanks for being here."},
        {"role": "Guest", "content": "Thanks Alex, it's great to be on the show. I'm excited to talk about where AI is heading."},
        {"role": "Host", "content": "Let's dive right in. What's the most exciting development in AI right now that most people haven't heard about?"},
        {"role": "Guest", "content": "I think it's the progress in smaller, more efficient models. We're seeing models that run on your phone but perform like giant systems from two years ago."},
        {"role": "Host", "content": "That is fascinating. Does this mean we'll all have personal AI assistants soon?"},
        {"role": "Guest", "content": "Absolutely. Within two years, I believe every smartphone will have a capable local AI that understands context, remembers conversations, and helps with daily tasks without sending data to the cloud."},
        {"role": "Host", "content": "What about privacy concerns with that?"},
        {"role": "Guest", "content": "Local AI actually solves the biggest privacy problem. Your data never leaves your device. That's a game changer for healthcare, finance, and personal communications."},
    ]
    ok1, t1 = test_longform(short_script, "Short single-pass (~200 words)", expected_chunks=1)

    # Test 2: Medium chunked (~600 words, should split into 2 chunks)
    medium_script = [
        {"role": "Host", "content": "Welcome to Tech Talks Today. I'm your host, Alex. Joining me is Dr. Sarah Chen, a leading researcher in artificial intelligence, and Marcus Webb, a venture capitalist focused on deep tech. Sarah, Marcus, thanks for being here."},
        {"role": "Guest A", "content": "Thanks Alex, always a pleasure."},
        {"role": "Guest B", "content": "Happy to be here, Alex."},
        {"role": "Host", "content": "Let's start with the big picture. Sarah, where is AI heading in the next five years?"},
        {"role": "Guest A", "content": "We're moving from generative AI to agentic AI. Instead of models that just write text or generate images, we'll have systems that can plan, execute tasks, and collaborate with humans over long time horizons. Think of an AI research assistant that can read papers, run experiments, and write reports over the course of weeks."},
        {"role": "Guest B", "content": "From an investment perspective, the companies building the infrastructure for these agents are getting the most attention. But I think the real winners will be the applications that solve specific problems. Healthcare diagnostics, legal document review, and software engineering are already seeing massive productivity gains."},
        {"role": "Host", "content": "Marcus, you mentioned healthcare. Sarah, what are the technical barriers to AI in medicine?"},
        {"role": "Guest A", "content": "The biggest challenge is reliability and hallucination. In creative writing, a hallucination is amusing. In medicine, it could be fatal. We need models that know what they don't know and can say 'I'm not confident about this diagnosis, you need a human expert.' That kind of calibrated uncertainty is still an open research problem."},
        {"role": "Guest B", "content": "And the regulatory landscape is complex. FDA approval for AI diagnostics takes years. Startups need to navigate that while also building better models. It's expensive and slow, which favors well-funded incumbents."},
        {"role": "Host", "content": "What about the open source movement? Are smaller players being squeezed out?"},
        {"role": "Guest A", "content": "Actually, open source is more vibrant than ever. Meta's Llama models, Mistral, and a thriving community of fine-tuned variants mean that a small team with a good idea can compete. The moat for big labs isn't the model weights anymore, it's the compute and the data flywheel."},
        {"role": "Guest B", "content": "I agree. I've seen seed-stage companies build impressive products on top of open weights. The key is domain expertise and proprietary data, not necessarily training from scratch."},
        {"role": "Host", "content": "Final question for both of you. What's one prediction each for AI in 2030?"},
        {"role": "Guest A", "content": "I think we'll have AI systems that are genuine scientific collaborators. They'll propose hypotheses, design experiments, and discover things no human would have thought to look for. Nobel Prizes won with AI assistance by 2030."},
        {"role": "Guest B", "content": "And I think the AI bubble will have popped and rebuilt by then. We'll see a wave of consolidation, but the surviving companies will be orders of magnitude more valuable because they'll actually be profitable. The hype cycle is real, but so is the underlying technology."},
        {"role": "Host", "content": "Excellent insights from both of you. Thank you Dr. Sarah Chen and Marcus Webb for joining us today."},
    ]
    ok2, t2 = test_longform(medium_script, "Medium chunked (~600 words, 3 speakers)", expected_chunks=2)

    # Test 3: Long multi-speaker panel (~1000 words, should split into 3 chunks)
    long_script = [
        {"role": "Host", "content": "Welcome to the Future of Technology Summit. I'm your moderator, Alex Rivera. Today we have an incredible panel: Dr. Sarah Chen from MIT's AI Lab, Marcus Webb from Horizon Ventures, and Priya Patel, CEO of NeuroLink Systems. Welcome everyone."},
        {"role": "Guest A", "content": "Thank you Alex, honored to be here."},
        {"role": "Guest B", "content": "Pleasure to join the discussion."},
        {"role": "Guest C", "content": "Thanks for having me, Alex."},
        {"role": "Host", "content": "Sarah, let's start with you. Your lab recently published a paper on neuromorphic computing. Can you explain what that means for non-specialists?"},
        {"role": "Guest A", "content": "Of course. Traditional computers are digital, they process information in zeros and ones. Neuromorphic chips mimic the structure of biological brains. They use analog signals and spike-based communication, which makes them incredibly energy efficient for AI workloads. We're talking about a thousand-fold reduction in power consumption for certain tasks."},
        {"role": "Guest C", "content": "And that's exactly why NeuroLink is investing heavily in this space. Our medical implants need to run sophisticated signal processing for years on a tiny battery. Neuromorphic architectures are the only viable path forward for brain-computer interfaces that are actually practical."},
        {"role": "Guest B", "content": "From an investment standpoint, neuromorphic computing is still early stage. The hardware is promising but the software ecosystem is immature. Companies need compilers, frameworks, and developer tools. That's where I see the near-term opportunity, in the picks and shovels rather than the end applications."},
        {"role": "Host", "content": "Priya, you mentioned brain-computer interfaces. How close are we to helping paralyzed patients walk again using these technologies?"},
        {"role": "Guest C", "content": "We're closer than most people realize. Last year, we had a patient control a robotic arm with just their thoughts, with enough precision to feed themselves. The challenge now is making the system reliable outside the lab. The brain moves, the implant shifts slightly, and the signal quality degrades. We're working on adaptive algorithms that recalibrate in real time."},
        {"role": "Guest A", "content": "The signal processing challenge is fascinating from a machine learning perspective. The brain generates enormous amounts of noisy data. Separating the signal from the noise requires techniques borrowed from astrophysics and quantum computing. It's one of the most interdisciplinary fields I've ever worked in."},
        {"role": "Host", "content": "Marcus, are VCs actually funding brain-computer interface companies? The regulatory path seems daunting."},
        {"role": "Guest B", "content": "They are, but selectively. The FDA breakthrough device program has actually been quite supportive for companies with compelling early data. The challenge is the long time horizon. Investors need to be comfortable with ten-year holding periods. That's why you're seeing more strategic corporate investors than traditional venture funds in this space."},
        {"role": "Guest C", "content": "Exactly. Our Series B was led by a major pharmaceutical company, not a traditional VC. They see BCIs as the ultimate drug delivery monitoring platform. Imagine adjusting medication dosage in real time based on actual brain state rather than subjective patient reports."},
        {"role": "Host", "content": "Sarah, shifting gears slightly. There's a lot of concern about AI safety and alignment. Is the research community taking this seriously enough?"},
        {"role": "Guest A", "content": "I think we're taking it seriously but we're divided on the approach. Some researchers want to slow down capability development to focus on safety. Others believe the best way to make AI safe is to make it more capable, so it can help us solve the alignment problem. I personally think we need both approaches in parallel."},
        {"role": "Guest B", "content": "The market forces are pushing toward capability. Companies that pause for safety lose to competitors that don't. We probably need international agreements or regulatory frameworks to create coordination. Without that, it's a classic race to the bottom."},
        {"role": "Guest C", "content": "In medical AI, we have a natural regulatory framework that forces safety. The FDA won't approve a device that hasn't been rigorously tested. I wonder if general AI systems need something similar, a pre-market approval process for models above a certain capability threshold."},
        {"role": "Host", "content": "That's a provocative idea. Marcus, would the tech industry accept that?"},
        {"role": "Guest B", "content": "Reluctantly, yes. If the alternative is a complete ban or public backlash that destroys the industry, thoughtful regulation is preferable. The key is having regulators who understand the technology. We can't have people who've never used ChatGPT writing rules for superintelligent systems."},
        {"role": "Guest A", "content": "And the research community needs to be involved in shaping those regulations. Right now, there's too much adversarial tension between labs and governments. We need constructive dialogue, and that requires both sides to invest in understanding each other."},
        {"role": "Host", "content": "Priya, last word to you. What's the one thing you want our audience to remember about the future of technology?"},
        {"role": "Guest C", "content": "That technology is a tool, not a destiny. We get to choose how we use it. Brain-computer interfaces could create a dystopia of surveillance and control, or they could restore mobility, communication, and independence to millions of people. The difference is in the choices we make today about governance, ethics, and access."},
        {"role": "Host", "content": "Powerful words. Thank you all for an incredible discussion. To our audience, thank you for joining the Future of Technology Summit."},
    ]
    ok3, t3 = test_longform(long_script, "Long panel (~1000 words, 4 speakers)", expected_chunks=3)

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Short  (~200w):  {'PASS' if ok1 else 'FAIL'} in {t1:.1f}s")
    print(f"Medium (~600w):  {'PASS' if ok2 else 'FAIL'} in {t2:.1f}s")
    print(f"Long  (~1000w):  {'PASS' if ok3 else 'FAIL'} in {t3:.1f}s")


if __name__ == "__main__":
    main()
