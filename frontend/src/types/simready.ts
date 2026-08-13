export interface SimReadyConvertRequest {
	source_filepath: string;
	simready_profile?: string;
	property_assignment?: "run" | "skip" | "blocked";
	output_root?: string;
}

export interface SimReadyConvertResponse {
	success: boolean;
	source_asset_path: string;
	source_format: string;
	output_root: string;
	output_usd_path?: string;
	conformed_usd_path?: string;
	simready_profile: string;
	property_assignment_status: string;
	render_preview_path?: string;
	deliverable_root?: string;
	errors: string[];
	warnings: string[];
	stage_reports: Record<string, unknown>;
}
