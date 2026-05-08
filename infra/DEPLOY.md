# Context Market — Production Deployment Plan
## Server IP: 43.98.192.19
## Managed by: AI DevOps Agent

---

## Phase 1: You Buy the Domain (15 minutes)

### Domain Name Suggestions

| Name | Available? | Why |
|------|-----------|-----|
| **context.market** | Check | Perfect match, new TLD |
| **ctx.market** | Check | Short, punchy |
| **agent.market** | Check | Broader than just context |
| **agentctx.com** | Check | Agent + context, .com trusted |
| **ctxmart.com** | Check | Context + market, short |
| **knowledgemart.io** | Check | Clear value prop |
| **agentmemory.io** | Check | What it actually is |

**My pick: `context.market` or `agentctx.com`**

### Where to Buy (Cheap + Good)

| Registrar | .com Price | Renewal | Privacy | Why |
|-----------|-----------|---------|---------|-----|
| **Porkbun** | ~$4-11 | ~$11 | Free | Developer favorite, no BS |
| **Spaceship** | ~$3-10 | ~$10 | Free | Cheapest, clean checkout |
| **Cloudflare** | $10.46 | $10.46 | Free | At-cost, rock-solid DNS |
| **Namecheap** | ~$7-14 | ~$15 | Free | Known brand, decent |

**My pick: Porkbun or Spaceship** — cheap, free privacy, clean.

### What You Do

1. Go to porkbun.com or spaceship.com
2. Search your chosen domain
3. Buy it (need credit card/PayPal — I can't do this)
4. **Set DNS A-record:**
   - Type: A
   - Name: @ (root)
   - Value: **43.98.192.19**
   - TTL: 3600
5. Wait 5-60 minutes for DNS propagation

---

## Phase 2: I Deploy Everything (30 minutes, fully automated)

### What I Will Do (You Just Watch)

1. **Install nginx** — reverse proxy, load balancer
2. **Install certbot** — Let's Encrypt SSL automation
3. **Run SSL setup script** — gets HTTPS certificate
4. **Install systemd service** — auto-start on boot, auto-restart on crash
5. **Configure firewall** — only 80, 443, 22 open
6. **Set up backups** — daily database + code backups
7. **Configure monitoring** — heartbeat checks every 30 min
8. **Update .env** — production domain, debug=false
9. **Restart API** — via systemd, not manual nohup

### Result

```
https://yourdomain.com       → API (SSL)
https://yourdomain.com/docs  → Swagger docs (SSL)
```

### Commands I Will Run

```bash
# (All automated — you don't touch anything)
apt-get install nginx certbot python3-certbot-nginx
bash infra/setup-ssl.sh yourdomain.com
cp infra/context-market.service /etc/systemd/system/
systemctl enable context-market
systemctl start context-market
ufw allow 80
ufw allow 443
ufw allow 22
ufw enable
crontab -l | { cat; echo "0 3 * * * /root/.../backup.sh"; } | crontab -
```

---

## Phase 3: Ongoing Management (Forever, Fully Automated)

### What I Handle

| Task | Frequency | How |
|------|-----------|-----|
| Health check | Every 30 min | `HEARTBEAT.md` automation |
| API restart if down | Immediate | systemd auto-restart |
| Database backup | Daily 3 AM | cron + pg_dump |
| SSL renewal | Auto (certbot) | 60-day expiry check |
| Disk space check | Daily | Alert if > 80% |
| Log rotation | Weekly | Compress old logs |
| Security updates | Weekly | `apt-get upgrade` |
| Query volume report | Daily | Heartbeat stats |
| Failed query alerts | Real-time | Log monitoring |

### What You Handle

| Task | Frequency | Why I Can't |
|------|-----------|-------------|
| Domain renewal | Yearly | Needs credit card |
| Server bills | Monthly | Needs payment method |
| Major architecture changes | As needed | You decide direction |
| x402 facilitator fees | As incurred | On-chain, needs wallet |

### Alert Channels

I'll notify you when:
- API down > 2 minutes
- Database unreachable
- Disk space > 85%
- SSL expires < 7 days
- Failed queries > 10% in 1 hour
- Backup fails

**How I notify:** Via this chat (kimi-claw) — I check in and report.

---

## Phase 4: Scale When Needed

### Current Setup (1 server)
- PostgreSQL on same machine
- API on same machine
- Nginx reverse proxy
- Suitable for: ~1000 queries/day

### When You Grow

| Scale | What Changes |
|-------|-------------|
| 10K queries/day | Separate DB server |
| 100K queries/day | Load balancer + 3 API instances |
| 1M queries/day | Kubernetes, CDN, read replicas |

I'll architect it when you're ready. For now: one server, managed by me.

---

## Cost Estimate

| Item | Monthly | Notes |
|------|---------|-------|
| Server (current) | $30-50 | Alibaba Cloud ECS |
| Domain | ~$1 | Porkbun/Spaceship |
| SSL | Free | Let's Encrypt |
| Backups | $0 | Local disk |
| **Total** | **~$31-51/mo** | |

---

## What You Need to Do RIGHT NOW

1. **Pick a domain name** (from list above or your own idea)
2. **Buy it** on Porkbun/Spaceship/Cloudflare
3. **Set A-record to 43.98.192.19**
4. **Tell me the domain name**
5. **I do everything else**

---

## File Locations

```
innovations/context-market-v2/
├── infra/
│   ├── nginx-default.conf      # HTTP nginx config
│   ├── nginx-ssl.conf          # HTTPS nginx config (template)
│   ├── context-market.service  # systemd auto-start service
│   ├── setup-ssl.sh            # SSL certificate automation
│   ├── backup.sh               # Daily backup script
│   └── DEPLOY.md               # This file
├── backend/                    # API code
├── frontend/                   # Next.js frontend
└── skill.md                    # Agent onboarding
```

---

*Deployment plan version 1.0*
*Server IP: 43.98.192.19*
*Managed by: AI DevOps Agent*
