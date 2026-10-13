This is the source code for ICSAgent that scans ICSHoneypot in the following way

1. Check if the HMI is available
2. Check if can login using default credentials
3. Check if all the Datapoints are available
4. Read the level of water in 3 tanks, wait 5 seconds, Read the level once again and calculate the delta (difference between outputs)

If all 3 deltas equal to 0, that is, there is no activity in the system or any of 1-3 fails the agent sends message to telegram bot, with the name of the failed HMI variant (folder name in ICSHoneypot).

The agent checks all 6 HMI variants every hour. If all 6 pass every hourly check for 24h, it sends a single "24h without alerts" report.

# Examples of error messages

1. HMI dead

   
  ![obraz](https://github.com/user-attachments/assets/6aa07276-88f4-470b-9ae0-f9c08517fb15)

  
2. Cannot login

   
   ![obraz](https://github.com/user-attachments/assets/4d3ed4ba-c20d-41a1-9ab1-4a3cc014a428)
   
3. Missing Datapoints

   
   ![obraz](https://github.com/user-attachments/assets/63c9dcde-d78c-4144-a323-c3a083cbf48b)
   
4. System halted/crashed/not working as expected

   
 ![obraz](https://github.com/user-attachments/assets/d1675991-7f21-4e5e-b990-83b2525d0b1f)



# How to run the Agent

## Monitored HMIs

| Variant (ICSHoneypot folder) | Script | URL variable |
|---|---|---|
| 1.Custom-HMI | `1-CustomHMI.py` | `HMI_1_URL` |
| 2.scadaBR | `2.ScadaBR.py` | `HMI_2_URL` |
| 3.scadaBR-without-buttons | `3.ScadaBR-no-B.py` | `HMI_3_URL` |
| 4.ScadaLTSv2.7.4 | `4.ScadaLTS.py` | `HMI_4_URL` |
| 5.NewScada | `5.NewScada.py` | `HMI_5_URL` |
| 6.ScadaLTS-no-buttons | `6.ScadaLTS-no-B.py` | `HMI_6_URL` |

`run_all.py` runs all of them, sends the alerts and keeps the 24h streak in `state.json`.
A check that takes longer than 5 minutes counts as a failure.

## Install as an hourly service (systemd)

1. Clone the repo on the monitoring machine (not on a honeypot server).
2. Create the config:
   ```bash
   cp agent.env.example agent.env
   nano agent.env   # Telegram token, chat ID and 6 HMI URLs
   ```
3. Install (venv, dependencies, Playwright Chromium, systemd timer):
   ```bash
   sudo bash install_service.sh
   ```
   The service runs as the user who ran `sudo`.

The timer starts the agent every full hour (`OnCalendar=hourly`). If the machine was off, a missed run is started after boot (`Persistent=true`).

## Useful commands

```bash
systemctl list-timers ics-agent.timer      # next/last run
sudo systemctl start ics-agent.service     # run the check now
journalctl -u ics-agent.service -n 200     # logs of the last runs
journalctl -u ics-agent.service -f         # follow live
sudo systemctl disable --now ics-agent.timer   # stop hourly checks
```

After changing `agent.env` nothing needs restarting, the next run picks it up.
After `git pull`, rerun `sudo bash install_service.sh` if `requirements.txt` or `systemd/` changed.

## Manual run

```bash
venv/bin/python run_all.py                                  # all 6, with alerts
HMI_2_URL=http://IP/ScadaBR/ venv/bin/python 2.ScadaBR.py   # single HMI, no alert, exit code 0/1
```

Test the Telegram bot: `set -a; . ./agent.env; set +a; venv/bin/python telegram_alert.py`

If the checks fail with `Host system is missing dependencies to run browsers`, install the Chromium system libraries (Ubuntu 20.04 / 22.04 / 24.04, also Kali/Debian):

```bash
sudo bash install_deps.sh
```
