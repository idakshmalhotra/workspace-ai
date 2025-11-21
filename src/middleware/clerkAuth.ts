import { Request, Response, NextFunction } from 'express';
import { clerkClient } from '@clerk/clerk-sdk-node';

interface ClerkUser {
  id: string;
  emailAddresses: Array<{ emailAddress: string }>;
  firstName?: string;
  lastName?: string;
}

interface AuthenticatedRequest extends Request {
  auth?: {
    userId: string;
    user: ClerkUser | null;
  };
}

export const requireAuth = async (
  req: AuthenticatedRequest,
  res: Response,
  next: NextFunction
): Promise<void> => {
  try {
    // Get the Authorization header
    const authHeader = req.headers.authorization;
    
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      res.status(401).json({ error: 'No authentication token provided' });
      return;
    }

    // Extract the token
    const token = authHeader.replace('Bearer ', '');

    // Verify the token with Clerk
    const sessionToken = await clerkClient.verifyToken(token);
    
    if (!sessionToken || !sessionToken.sub) {
      res.status(401).json({ error: 'Invalid or expired token' });
      return;
    }

    // Get user information from Clerk
    const user = await clerkClient.users.getUser(sessionToken.sub);

    // Attach user info to request
    req.auth = {
      userId: sessionToken.sub,
      user: user as unknown as ClerkUser,
    };

    next();
  } catch (error) {
    console.error('Clerk authentication error:', error);
    res.status(401).json({ error: 'Authentication failed', details: (error as Error).message });
  }
};

// Optional: Middleware that doesn't fail if no auth token (for public routes)
export const optionalAuth = async (
  req: AuthenticatedRequest,
  res: Response,
  next: NextFunction
): Promise<void> => {
  try {
    const authHeader = req.headers.authorization;
    
    if (authHeader && authHeader.startsWith('Bearer ')) {
      const token = authHeader.replace('Bearer ', '');
      const sessionToken = await clerkClient.verifyToken(token);
      
      if (sessionToken && sessionToken.sub) {
        const user = await clerkClient.users.getUser(sessionToken.sub);
        req.auth = {
          userId: sessionToken.sub,
          user: user as unknown as ClerkUser,
        };
      }
    }
    
    next();
  } catch (error) {
    // Continue without auth if verification fails
    next();
  }
};

export default requireAuth;


