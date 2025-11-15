import express from "express";
import cors from "cors";
import dotenv from "dotenv";
import { createClient } from "@supabase/supabase-js";

dotenv.config();

const app = express();
app.use(cors());
app.use(express.json());

const supabase = createClient(
  'https://nuuhmgtuphxxhbuwqufp.supabase.co',
  process.env.SUPABASE_KEY
);

const TABLE = 'scrapedata';

app.get("/api/data", async (req, res) => {
  const { data, error } = await supabase.from(TABLE).select("*").order("DA_Number", { ascending: false });

  if (error) {
    console.log(error)
    return res.status(500).json({ error: error.message });
  }
  console.log(data)
  res.json(data);
});

app.listen(5000, () => console.log("API running on http://localhost:5000"));
