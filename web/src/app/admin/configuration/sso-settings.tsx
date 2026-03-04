'use client';

import { Config } from '@/api';
import { Badge } from '@/components/ui/badge';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';
import {
  CheckCircle2,
  ExternalLink,
  Key,
  KeyRound,
  Shield,
  XCircle,
} from 'lucide-react';
import { FaGithub, FaGoogle } from 'react-icons/fa6';

type SsoProvider = {
  id: string;
  name: string;
  icon: React.ReactNode;
  description: string;
  envVars: string[];
  enabled: boolean;
};

export const SsoSettings = ({ config }: { config?: Config }) => {
  const loginMethods = config?.login_methods || [];

  const providers: SsoProvider[] = [
    {
      id: 'google',
      name: 'Google OAuth',
      icon: <FaGoogle className="size-5" />,
      description:
        'Allow users to sign in with their Google account via OAuth 2.0',
      envVars: ['GOOGLE_OAUTH_CLIENT_ID', 'GOOGLE_OAUTH_CLIENT_SECRET'],
      enabled: loginMethods.includes('google'),
    },
    {
      id: 'github',
      name: 'GitHub OAuth',
      icon: <FaGithub className="size-5" />,
      description:
        'Allow users to sign in with their GitHub account via OAuth 2.0',
      envVars: ['GITHUB_OAUTH_CLIENT_ID', 'GITHUB_OAUTH_CLIENT_SECRET'],
      enabled: loginMethods.includes('github'),
    },
    {
      id: 'auth0',
      name: 'Auth0',
      icon: <Shield className="size-5" />,
      description:
        'Enterprise SSO via Auth0 supporting SAML, OIDC, and social connections',
      envVars: ['AUTH_TYPE=auth0', 'AUTH0_DOMAIN', 'AUTH0_CLIENT_ID'],
      enabled: config?.auth?.auth0 !== undefined,
    },
    {
      id: 'oidc',
      name: 'OIDC / Authing / Logto',
      icon: <KeyRound className="size-5" />,
      description:
        'Generic OpenID Connect support via Authing or Logto identity providers',
      envVars: [
        'AUTH_TYPE=authing|logto',
        'AUTHING_DOMAIN / LOGTO_DOMAIN',
        'AUTHING_APP_ID / LOGTO_APP_ID',
      ],
      enabled: false,
    },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Key className="size-5" />
          Single Sign-On (SSO)
        </CardTitle>
        <CardDescription>
          Configure authentication providers for your ApeRAG instance. SSO
          providers are configured via environment variables.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {providers.map((provider, index) => (
          <div key={provider.id}>
            {index > 0 && <Separator className="mb-4" />}
            <div className="flex items-start gap-4">
              <div className="bg-muted flex size-10 shrink-0 items-center justify-center rounded-lg">
                {provider.icon}
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{provider.name}</span>
                  {provider.enabled ? (
                    <Badge
                      variant="default"
                      className="bg-green-600 text-[10px]"
                    >
                      <CheckCircle2 className="mr-0.5 size-2.5" />
                      Connected
                    </Badge>
                  ) : (
                    <Badge variant="secondary" className="text-[10px]">
                      <XCircle className="mr-0.5 size-2.5" />
                      Not configured
                    </Badge>
                  )}
                </div>
                <p className="text-muted-foreground mt-1 text-sm">
                  {provider.description}
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {provider.envVars.map((envVar) => (
                    <code
                      key={envVar}
                      className={cn(
                        'rounded px-1.5 py-0.5 font-mono text-xs',
                        provider.enabled
                          ? 'bg-green-500/10 text-green-600'
                          : 'bg-muted text-muted-foreground',
                      )}
                    >
                      {envVar}
                    </code>
                  ))}
                </div>
              </div>
            </div>
          </div>
        ))}

        <Separator />
        <div className="text-muted-foreground flex items-center gap-2 text-xs">
          <ExternalLink className="size-3" />
          <span>
            SSO providers are configured via environment variables in your{' '}
            <code className="bg-muted rounded px-1 py-0.5">.env</code> file or
            deployment configuration. Set{' '}
            <code className="bg-muted rounded px-1 py-0.5">
              AUTH_TYPE
            </code>{' '}
            and the corresponding provider credentials to enable SSO.
          </span>
        </div>
      </CardContent>
    </Card>
  );
};
