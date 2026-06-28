require("dotenv").config();
const express = require("express");
const stripe = require("stripe")(process.env.STRIPE_SECRET_KEY);

const app = express();
const PORT = process.env.PORT || 3000;
const DOMAIN = process.env.DOMAIN || `http://localhost:${PORT}`;
const PRICE_CENTS = parseInt(process.env.PRICE_CENTS || "2900", 10);

// ── in-memory paid session store ─────────────────────────────────────────────
// In production: replace with a database lookup keyed on customer email/ID.
const paidSessions = new Set();

// ── static files ─────────────────────────────────────────────────────────────
app.use(express.static("public"));

// ── Stripe webhook (must be raw body — registered BEFORE express.json) ───────
app.post(
  "/webhook",
  express.raw({ type: "application/json" }),
  async (req, res) => {
    const sig = req.headers["stripe-signature"];
    let event;

    try {
      event = stripe.webhooks.constructEvent(
        req.body,
        sig,
        process.env.STRIPE_WEBHOOK_SECRET
      );
    } catch (err) {
      console.error("Webhook signature mismatch:", err.message);
      return res.status(400).send(`Webhook Error: ${err.message}`);
    }

    if (event.type === "checkout.session.completed") {
      const session = event.data.object;
      if (session.payment_status === "paid") {
        paidSessions.add(session.id);
        console.log(`✅ Node activated  session=${session.id}`);
      }
    }

    res.json({ received: true });
  }
);

app.use(express.json());

// ── create Checkout session ───────────────────────────────────────────────────
app.post("/create-checkout-session", async (req, res) => {
  try {
    const session = await stripe.checkout.sessions.create({
      payment_method_types: ["card"],
      line_items: [
        {
          price_data: {
            currency: "usd",
            product_data: {
              name: "ANR Cosmic Net — Full Access",
              description:
                "Unlock all nodes: AI Core · Music Vault · Mystery School · Marketplace · Node Map",
            },
            unit_amount: PRICE_CENTS,
          },
          quantity: 1,
        },
      ],
      mode: "payment",
      // Stripe replaces {CHECKOUT_SESSION_ID} server-side before the redirect
      success_url: `${DOMAIN}/success?session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: `${DOMAIN}/cancel.html`,
    });

    res.json({ url: session.url });
  } catch (err) {
    console.error("Checkout error:", err.message);
    res.status(500).json({ error: err.message });
  }
});

// ── success redirect ──────────────────────────────────────────────────────────
// Stripe sends the user here after payment. We verify the session,
// register it as paid, then hand off to the Cosmic Net dashboard.
app.get("/success", async (req, res) => {
  const { session_id } = req.query;
  if (!session_id) return res.redirect("/cancel.html");

  try {
    const session = await stripe.checkout.sessions.retrieve(session_id);

    if (session.payment_status === "paid") {
      paidSessions.add(session.id);
      // The session ID is long and unguessable — acts as the access token.
      return res.redirect(`/cosmic-net.html?access=${session_id}`);
    }

    res.redirect("/cancel.html");
  } catch (err) {
    console.error("Session retrieve error:", err.message);
    res.redirect("/cancel.html");
  }
});

// ── access verification endpoint (called by cosmic-net.html on load) ─────────
app.get("/verify-access", (req, res) => {
  const { token } = req.query;
  const active = Boolean(token && paidSessions.has(token));
  res.json({ active });
});

// ── health check ─────────────────────────────────────────────────────────────
app.get("/health", (_req, res) => res.json({ status: "ok" }));

app.listen(PORT, () => {
  console.log(`🌌 Cosmic Net  ${DOMAIN}`);
});
