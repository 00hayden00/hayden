# Running SRM-Bot on your laptop, controlling it from your office desktop

The design goal: the bot and all its memory (`data/srmbot.db`, `config.json`) live **only on
your laptop**. Your office desktop is just a remote keyboard/screen into it — nothing lead-
related is stored on the desktop or in any cloud service.

## Recommended: Tailscale + SSH (free, ~10 minutes)

Tailscale creates a private encrypted network between just your two machines, so the laptop
is reachable from the desktop even across different networks (home vs. office) without any
router/firewall changes.

**On the laptop (the host):**
1. Install Tailscale (tailscale.com/download) and sign in.
2. Enable an SSH server:
   - Windows: Settings → System (or Apps) → Optional Features → add **OpenSSH Server**, then
     set the `sshd` service to start automatically.
   - macOS: System Settings → General → Sharing → **Remote Login**.
3. Note the laptop's Tailscale name (e.g. `haydens-laptop`).
4. Keep the laptop plugged in with sleep disabled while you're working (Windows: Power &
   battery → "Never" sleep when plugged in).

**On the office desktop (the remote control):**
1. Install Tailscale, sign in with the same account.
2. Open a terminal:
   ```
   ssh you@haydens-laptop
   cd path/to/SRM-Bot
   python -m srm_bot next
   ```

That's it — every SRM-Bot command works identically over SSH because it's a terminal app.

## Alternative: full desktop remote control

If you'd rather see the laptop's whole screen (e.g. to click around DemandConversions in a
browser on the laptop):

- **Chrome Remote Desktop** — free, easiest, works through any firewall.
- **Windows Remote Desktop (RDP)** over Tailscale — laptop needs Windows Pro; connect to the
  laptop's Tailscale address from the desktop's Remote Desktop app.
- **RustDesk** — free, open source, similar to TeamViewer.

## Getting daily reports onto the laptop from the desktop

If you download a CRM export at the office, copy it over the same private network:

```
scp dc_daily_report.csv you@haydens-laptop:~/reports/
ssh you@haydens-laptop "cd SRM-Bot && python -m srm_bot import ~/reports/dc_daily_report.csv --source demandconversions"
```

## Security basics

- Lead files contain consumer PII — keep them on the laptop, delete stray downloads from the
  desktop after copying them over.
- Turn on full-disk encryption on the laptop (BitLocker / FileVault) since it now holds the
  lead database.
- Tailscale connections are end-to-end encrypted and limited to devices on your account; don't
  expose SSH/RDP directly to the internet.
