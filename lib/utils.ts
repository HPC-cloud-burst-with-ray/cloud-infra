import {StackProps} from 'aws-cdk-lib';

export interface EC2StackProps extends StackProps {
    sshPubKey: string;
    cpuType: string;
    instanceSize: string;
    workerNodeNum: number;
  }