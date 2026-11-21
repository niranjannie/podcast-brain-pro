# Setup Troubleshooting — Steps 2 & 3

## Step 2: Install Backend (Common Problems)

### Problem: `pip install -r requirements.txt` fails

**Check your Python version:**
```bash
python3 --version
```
Must be **3.10 or higher**. If you have 3.9, install Python 3.10+ from python.org.

**If you see "No module named pip":**
```bash
python3 -m ensurepip --upgrade
```

**If installation hangs or is slow:**
This is normal — some packages (torch, transformers) are large. Just wait 5-10 minutes.

**If you see compiler errors (gcc, clang, etc.):**
On macOS, install Xcode command line tools:
```bash
xcode-select --install
```

---

### Problem: `pip install -e .` in vibevoice-src fails

**Make sure you're in the vibevoice-src folder:**
```bash
cd podcast-brain-pro/vibevoice-src
pip install -e .
```

**If you see "No such file or directory: setup.py":**
Check that vibevoice-src exists:
```bash
ls podcast-brain-pro/vibevoice-src/
```
If it's missing, the repo didn't clone fully. Re-clone.

**If install fails with build errors:**
```bash
pip install --upgrade pip setuptools wheel
pip install -e .
```

---

### Problem: Virtual environment not working

**If `source .venv/bin/activate` says "No such file":**
You skipped creating it. Do:
```bash
cd voice-service
python3 -m venv .venv
source .venv/bin/activate
```

**If you're on Windows (not macOS/Linux):**
Use this instead of `source`:
```bash
.venv\Scripts\activate
```

---

## Step 3: Configure API Keys (Common Problems)

### You only need ONE key to start

Don't stress about filling in everything. You just need **one** working LLM provider for script generation.

### Easiest free option: GitHub Models

1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Give it a name like "Podcast Brain Pro"
4. Check the box for **"Models"** permission (or just give it all read permissions)
5. Click Generate
6. Copy the token

**In your `.env` file:**
```
GITHUB_PERSONAL_ACCESS_TOKEN=ghp_YOUR_TOKEN_HERE
```

That's it. GitHub Models gives you free GPT-4o access.

---

### Alternative: Dialogram (if GitHub doesn't work)

1. Go to https://dialogram.me/
2. Sign up
3. Go to API Keys section
4. Copy your key

**In your `.env` file:**
```
DIALOGRAM_API_KEY=your_key_here
```

---

### For Indian languages (optional)

Only needed if you want Hindi, Kannada, Tamil, etc.

1. Go to https://www.sarvam.ai/
2. Sign up
3. Get an API key from their dashboard

**In your `.env` file:**
```
SARVAM_API_KEY=your_key_here
```

---

### Quick Check: Is my key working?

After adding your key to `.env`, start the backend:
```bash
cd voice-service
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

Then open http://localhost:8000/docs in your browser.

If the server starts without errors, your key is configured correctly.

If you see red error text about "No LLM provider configured," your key is wrong or missing.

---

## Still Stuck?

**Step 2 not working?**
1. What error message do you see? (Copy-paste the exact error)
2. What Python version? (`python3 --version`)
3. What operating system? (macOS/Windows/Linux)

**Step 3 not working?**
1. Which API provider did you try? (GitHub / Dialogram / other)
2. What does the error say when you start the backend?

Tell me the exact error and I'll fix it.
