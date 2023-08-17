import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import * as CdkTs from '../lib/cdk-ts-stack';

test('Init S3 Bucket created with correct permissions', () => {
    const app = new cdk.App();
    // WHEN
    const stack = new CdkTs.CdkTsStack(app, 'MyTestStack');
    // THEN
    const template = Template.fromStack(stack);
    template.resourceCountIs('AWS::S3::Bucket', 4);
    template.resourceCountIs('AWS::S3::BucketPolicy', 4);
    template.hasResourceProperties('AWS::S3::Bucket', {
        BucketEncryption: {
            "ServerSideEncryptionConfiguration": [
                { "ServerSideEncryptionByDefault": { "SSEAlgorithm": "AES256" } }
            ],
        }
    });
    template.hasResource('AWS::S3::Bucket', {
        DeletionPolicy: 'Delete',
        UpdateReplacePolicy: 'Delete',
    });
});

test('TranscribeTriggerFunction has correct base settings', () => {
    const app = new cdk.App();
    // WHEN
    const stack = new CdkTs.CdkTsStack(app, 'MyTestStack');
    // THEN
    const template = Template.fromStack(stack);
    template.resourceCountIs('AWS::Lambda::Function', 2);
    template.hasResourceProperties('AWS::Lambda::Function', {
        Handler: 'index.lambdaHandler',
        Runtime: 'nodejs16.x',
    });

});

