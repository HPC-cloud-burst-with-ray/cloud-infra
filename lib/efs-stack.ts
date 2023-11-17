import * as cdk from '@aws-cdk/core';
import * as ec2 from '@aws-cdk/aws-ec2';
import * as efs from '@aws-cdk/aws-efs';

export class EfsStack extends cdk.Stack {
    public readonly fileSystem: efs.FileSystem;

    constructor(scope: cdk.Construct, id: string, vpc: ec2.Vpc, props?: cdk.StackProps) {
        super(scope, id, props);

        // Create an EFS filesystem
        this.fileSystem = new efs.FileSystem(this, 'MyEfsFileSystem', {
            vpc,
            // Optional: Configure lifecycle policy, performance mode, etc.
            lifecyclePolicy: efs.LifecyclePolicy.AFTER_7_DAYS, // Example
            performanceMode: efs.PerformanceMode.GENERAL_PURPOSE,
            throughputMode: efs.ThroughputMode.BURSTING,
            encrypted: true,
        });
    }
}