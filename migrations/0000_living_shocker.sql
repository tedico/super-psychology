CREATE TYPE "public"."job_status" AS ENUM('queued', 'running', 'failed', 'done');--> statement-breakpoint
CREATE TYPE "public"."post_status" AS ENUM('pending', 'posted', 'failed');--> statement-breakpoint
CREATE TYPE "public"."user_role" AS ENUM('admin', 'user');--> statement-breakpoint
CREATE TABLE "jobs" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"series_id" uuid NOT NULL,
	"topic" text,
	"script" text,
	"title" text,
	"description" text,
	"hashtags" jsonb DEFAULT '[]'::jsonb NOT NULL,
	"status" "job_status" DEFAULT 'queued' NOT NULL,
	"stage_status" jsonb DEFAULT '{}'::jsonb NOT NULL,
	"asset_paths" jsonb DEFAULT '{}'::jsonb NOT NULL,
	"cost_usd" numeric(10, 4) DEFAULT '0' NOT NULL,
	"error" jsonb,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "posts" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"job_id" uuid NOT NULL,
	"platform" text NOT NULL,
	"remote_id" text,
	"remote_url" text,
	"status" "post_status" DEFAULT 'pending' NOT NULL,
	"posted_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "series" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"user_id" uuid NOT NULL,
	"name" text NOT NULL,
	"niche_prompt" text NOT NULL,
	"knowledge_source" text DEFAULT 'none' NOT NULL,
	"voice_id" text NOT NULL,
	"visual_style_prompt" text NOT NULL,
	"provider_config" jsonb DEFAULT '{"llm":"claude","tts":"elevenlabs","images":"nano-banana-2"}'::jsonb NOT NULL,
	"motion_config" jsonb DEFAULT '{"enabled":false,"firstNImages":3}'::jsonb NOT NULL,
	"schedule_cron" text DEFAULT '0 9 * * 1,3,5' NOT NULL,
	"platforms" jsonb DEFAULT '["youtube"]'::jsonb NOT NULL,
	"active" boolean DEFAULT true NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "users" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"email" text NOT NULL,
	"password_hash" text NOT NULL,
	"role" "user_role" DEFAULT 'user' NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "users_email_unique" UNIQUE("email")
);
--> statement-breakpoint
ALTER TABLE "jobs" ADD CONSTRAINT "jobs_series_id_series_id_fk" FOREIGN KEY ("series_id") REFERENCES "public"."series"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "posts" ADD CONSTRAINT "posts_job_id_jobs_id_fk" FOREIGN KEY ("job_id") REFERENCES "public"."jobs"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "series" ADD CONSTRAINT "series_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;