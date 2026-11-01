// Deliberately outdated dependencies – this service only exists as a scan target.
const express = require("express");
const jwt = require("jsonwebtoken");
const axios = require("axios");
const _ = require("lodash");

const app = express();
app.use(express.json());

const SECRET = process.env.JWT_SECRET || "demo-only-secret";
const users = { 1: { id: 1, name: "Ada", roles: ["admin"] } };

app.get("/health", (_req, res) => res.json({ status: "ok" }));

app.post("/token", (req, res) => {
  const token = jwt.sign({ sub: req.body.userId }, SECRET, { expiresIn: "1h" });
  res.json({ token });
});

app.get("/users/:id", (req, res) => {
  const user = _.get(users, req.params.id);
  return user ? res.json(_.pick(user, ["id", "name"])) : res.sendStatus(404);
});

app.get("/status/upstream", async (_req, res) => {
  const { status } = await axios.get("https://example.com", { timeout: 2000 });
  res.json({ upstream: status });
});

const port = Number(process.env.PORT || 3000);
app.listen(port, () => console.log(`demo-service listening on ${port}`));
