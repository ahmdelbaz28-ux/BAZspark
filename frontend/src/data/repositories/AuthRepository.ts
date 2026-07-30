/**
 * AuthRepository.ts — Concrete implementation of IAuthRepository.
 * Delegates HTTP network operations to fullApi while maintaining clean domain interface contract.
 */

import {
        AuthResponse,
        IAuthRepository,
        LoginCredentials,
        UserSession,
} from "../../domain/repositories/IAuthRepository";
import { fullApi } from "../../services/fullApi";

export class AuthRepository implements IAuthRepository {
        async login(credentials: LoginCredentials): Promise<AuthResponse> {
                try {
                        const res = await fullApi.login(credentials.username, credentials.password || "");
                        if (res?.success) {
                                return {
                                        success: true,
                                        token: res.token,
                                        session: {
                                                id: res.user?.id || "usr_default",
                                                username: res.user?.username || credentials.username,
                                                email: res.user?.email,
                                                role: res.user?.role || "engineer",
                                                permissions: res.user?.permissions || [],
                                                token: res.token,
                                        },
                                };
                        }
                        return {
                                success: false,
                                message: res?.message || "Invalid credentials",
                        };
                } catch (error) {
                        return {
                                success: false,
                                message: error instanceof Error ? error.message : "Authentication failed",
                        };
                }
        }

        async logout(): Promise<boolean> {
                try {
                        await fullApi.logout();
                        return true;
                } catch {
                        return false;
                }
        }

        async getCurrentSession(): Promise<UserSession | null> {
                try {
                        const res = await fullApi.getMe();
                        if (res?.data) {
                                return {
                                        id: res.data.id || "usr_current",
                                        username: res.data.username || "User",
                                        email: res.data.email,
                                        role: res.data.role || "engineer",
                                        permissions: res.data.permissions || [],
                                };
                        }
                        return null;
                } catch {
                        return null;
                }
        }

        async validateToken(token: string): Promise<boolean> {
                try {
                        const res = await fullApi.verifyToken(token);
                        return res?.success || false;
                } catch {
                        return false;
                }
        }
}

export const authRepository = new AuthRepository();
