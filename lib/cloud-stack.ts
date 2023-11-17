import { Stack, CfnOutput } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { CloudVpcResources } from './vpc';
import { EC2NodeResources } from './ec2';
import { EC2StackProps } from './utils';

export class CloudStack extends Stack {
  constructor(scope: Construct, id: string, props: EC2StackProps) {
    super(scope, id, props);

    const { sshPubKey, cpuType, instanceSize } = props;
    // assert cpuType is x86_64
    if (cpuType !== 'x86_64') {
      throw new Error('cpuType must be x86_64');
    }

    // create cloud side vpc
    const cloudVpc = new CloudVpcResources(this, 'CloudVPC');

    // create one cloud side ec2 instance (might be many nodes in the future)
    const cloudNode = new EC2NodeResources(this, 'CloudNode01', {
      vpc: cloudVpc.vpc,
      securityGroup: cloudVpc.cloudSecurityGroup,
      sshPubKey: sshPubKey,
      cpuType: cpuType,
      instanceSize: instanceSize,
      nodeType: 'CLOUD',
    });

    // SSM Command to start a session
    new CfnOutput(this, 'ssmCommand', {
      value: `aws ssm start-session --target ${cloudNode.instance.instanceId}`,
    });

    // SSH Command to connect to the EC2 Instance
    new CfnOutput(this, 'sshCommand', {
      value: `ssh ec2-user@${cloudNode.instance.instancePublicDnsName}`,
    });

  }
}
