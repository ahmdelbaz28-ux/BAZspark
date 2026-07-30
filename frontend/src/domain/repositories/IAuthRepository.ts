/**
 * IAuthRepository.ts — Domain Repository Interface for Authentication & Session Management.
 * Follows Clean Architecture (Domain Layer: Repository Abstraction).
 */

export interface LoginCredentials {
	username: string;
	password?: string;
}

export interface UserSession {
	id: string;
	username: string;
	email?: string;
	role: string;
	permissions?: string[];
	token?: string;
}

export interface AuthResponse {
	success: boolean;
	session?: UserSession;
	token?: string;
	message?: string;
}

export interface IAuthRepository {
	login(credentials: LoginCredentials): Promise<AuthResponse>;
	logout(): Promise<boolean>;
	getCurrentSession(): Promise<UserSession | null>;
	validateToken(token: string): Promise<boolean>;
}
