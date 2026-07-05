CREATE TABLE "research_findings" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"series_id" uuid NOT NULL,
	"topic" text NOT NULL,
	"claim" text NOT NULL,
	"paper_title" text NOT NULL,
	"paper_url" text NOT NULL,
	"used_by_job_id" uuid,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
ALTER TABLE "series" ALTER COLUMN "motion_config" SET DEFAULT '{"enabled":true,"firstNImages":2}'::jsonb;--> statement-breakpoint
ALTER TABLE "series" ADD COLUMN "music_config" jsonb DEFAULT '{"enabled":true,"path":"assets/music/China Dreaming.mp3"}'::jsonb NOT NULL;--> statement-breakpoint
ALTER TABLE "research_findings" ADD CONSTRAINT "research_findings_series_id_series_id_fk" FOREIGN KEY ("series_id") REFERENCES "public"."series"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "research_findings" ADD CONSTRAINT "research_findings_used_by_job_id_jobs_id_fk" FOREIGN KEY ("used_by_job_id") REFERENCES "public"."jobs"("id") ON DELETE set null ON UPDATE no action;