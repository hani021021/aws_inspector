import { GetCallerIdentityCommand, STSClient } from "@aws-sdk/client-sts";

// The default AWS profile on a developer machine may point to a customer account;
// without this check a missing AWS_PROFILE would silently query it.
export function checkAccount(actual: string | undefined, expected: string | undefined): string | null {
  if (!expected || !/^\d{12}$/.test(expected)) {
    return "EXPECTED_AWS_ACCOUNT_ID is not set to a 12-digit AWS account ID";
  }
  if (actual !== expected) {
    return `Credentials belong to AWS account ${actual ?? "unknown"}, expected ${expected}. Check AWS_PROFILE.`;
  }
  return null;
}

export async function currentAccount(): Promise<string | undefined> {
  const identity = await new STSClient({}).send(new GetCallerIdentityCommand({}));
  return identity.Account;
}
