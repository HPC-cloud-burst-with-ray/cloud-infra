#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { CloudStack } from '../lib/cloud-stack';
import { OnPremStack } from '../lib/on-prem-stack';
import { EC2StackProps } from '../lib/utils';
import * as fs from 'fs';

const appConfigFile = 'cdk-app-config.json';
const appConfig = JSON.parse(fs.readFileSync(appConfigFile, 'utf8'));
// console.log(appConfig);

const deployAccountConfig = appConfig.environment.CDK_DEPLOY_ACCOUNT;
const deployRegionConfig = appConfig.environment.CDK_DEPLOY_REGION;
console.log("AWS Account: ", deployAccountConfig);
console.log("AWS Region: ", deployRegionConfig);

const stackPropsOnPrem: EC2StackProps = {
  sshPubKey: appConfig.environment.SSH_PUB_KEY || ' ',
  cpuType: appConfig.environment.CPU_TYPE || 'x86_64',
  instanceSize: appConfig.onprem.INSTANCE_SIZE || 'LARGE',
  workerNodeNum: appConfig.onprem.WORKER_NODE_NUM || 1,
};
console.log("OnPrem StackProps: ", stackPropsOnPrem);

const stackPropsCloud: EC2StackProps = {
  sshPubKey: appConfig.environment.SSH_PUB_KEY || ' ',
  cpuType: appConfig.environment.CPU_TYPE || 'x86_64',
  instanceSize: appConfig.cloud.INSTANCE_SIZE || 'LARGE',
  workerNodeNum: appConfig.cloud.WORKER_NODE_NUM || 1,
};

console.log("Cloud StackProps: ", stackPropsCloud);

// require('dotenv').config();
// const stackProps: EC2StackProps = {
//   sshPubKey: process.env.SSH_PUB_KEY || ' ',
//   cpuType: process.env.CPU_TYPE || 'x86_64',
//   instanceSize: process.env.INSTANCE_SIZE || 'LARGE',
//   workerNodeNum: 1,
// };

// log stack props for debug
// console.log(stackProps);

const app = new cdk.App();
new CloudStack(app, 'CloudStack', {
  /* If you don't specify 'env', this stack will be environment-agnostic.
   * Account/Region-dependent features and context lookups will not work,
   * but a single synthesized template can be deployed anywhere. */

  /* Uncomment the next line to specialize this stack for the AWS Account
   * and Region that are implied by the current CLI configuration. */
  env: { account: process.env.CDK_DEFAULT_ACCOUNT, region: process.env.CDK_DEFAULT_REGION },
  // env: { account: '221930534130', region: 'us-east-1' },

  /* Uncomment the next line if you know exactly what Account and Region you
   * want to deploy the stack to. */
  // env: { account: '123456789012', region: 'us-east-1' },

  /* For more information, see https://docs.aws.amazon.com/cdk/latest/guide/environments.html */
  ...stackPropsCloud
});

new OnPremStack(app, 'OnPremStack', {
  env: { account: process.env.CDK_DEFAULT_ACCOUNT, region: process.env.CDK_DEFAULT_REGION },
  // env: { account: '221930534130', region: 'us-east-1' },

  ...stackPropsOnPrem
});

app.synth();