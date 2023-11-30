#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { CloudStack } from '../lib/cloud-stack';
import { OnPremStack } from '../lib/on-prem-stack';
import { EC2StackProps } from '../lib/utils';

require('dotenv').config();

const stackProps: EC2StackProps = {
  sshPubKey: process.env.SSH_PUB_KEY || ' ',
  cpuType: process.env.CPU_TYPE || 'x86_64',
  instanceSize: process.env.INSTANCE_SIZE || 'LARGE',
};

// log stack props for debug
console.log(stackProps);

const app = new cdk.App();
new CloudStack(app, 'CloudStack', {
  /* If you don't specify 'env', this stack will be environment-agnostic.
   * Account/Region-dependent features and context lookups will not work,
   * but a single synthesized template can be deployed anywhere. */

  /* Uncomment the next line to specialize this stack for the AWS Account
   * and Region that are implied by the current CLI configuration. */
  env: { account: process.env.CDK_DEFAULT_ACCOUNT, region: process.env.CDK_DEFAULT_REGION },

  /* Uncomment the next line if you know exactly what Account and Region you
   * want to deploy the stack to. */
  // env: { account: '123456789012', region: 'us-east-1' },

  /* For more information, see https://docs.aws.amazon.com/cdk/latest/guide/environments.html */
  ...stackProps
});

new OnPremStack(app, 'OnPremStack', {
  env: { account: process.env.CDK_DEFAULT_ACCOUNT, region: process.env.CDK_DEFAULT_REGION },
  ...stackProps
});

app.synth();