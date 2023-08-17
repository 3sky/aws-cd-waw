import { readFileSync } from 'fs';
import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as batch from '@aws-cdk/aws-batch-alpha';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as codebuild from 'aws-cdk-lib/aws-codebuild';
import * as codecommit from 'aws-cdk-lib/aws-codecommit';
import { S3EventSource } from 'aws-cdk-lib/aws-lambda-event-sources';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as triggers from 'aws-cdk-lib/triggers';
import * as snsSubscriptions from 'aws-cdk-lib/aws-sns-subscriptions';
import * as s3Notifications from "aws-cdk-lib/aws-s3-notifications";
import path = require('path');

const TranscribeTriggerFunctionCode = readFileSync('./assets/TranscribeTriggerFunction.js', 'utf-8');
const BatchTriggerFunctionCode = readFileSync('./assets/BatchTriggerFunction.js', 'utf-8');
const RunOnceFunctionCode = readFileSync('./assets/RunOnceFunction.js', 'utf-8');

export class CdkTsStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    cdk.Tags.of(this).add("description", "AWS CD - Video Localization");
    cdk.Tags.of(this).add("organization", "3sky.dev");
    cdk.Tags.of(this).add("owner", "kuba");

    const emailAddress = new cdk.CfnParameter(this, "subscriptionEmail", {
      type: "String",
      description: "Email address to receive notifications"
    });

    const getExistingVpc = ec2.Vpc.fromLookup(this, 'ImportVPC', { isDefault: true });

    const defaultBucketProps = {
      versioned: false,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    };

    const rowVideoS3bucket = new s3.Bucket(this, 'RowVideoS3bucket', {
      bucketName: cdk.Stack.of(this).account + "-initial-videos", ...defaultBucketProps
    });
    const transcribedVideoS3bucket = new s3.Bucket(this, 'TranscribedTextBucket', {
      bucketName: cdk.Stack.of(this).account + "-transcribed-to-review", ...defaultBucketProps
    });
    const videoToLocalisationS3bucket = new s3.Bucket(this, 'RideoToLocalisationS3bucket', {
      bucketName: cdk.Stack.of(this).account + "-transcribed-after-review", ...defaultBucketProps
    });
    const videoOutputS3bucket = new s3.Bucket(this, 'VideoOutputS3bucket', {
      bucketName: cdk.Stack.of(this).account + "-final-videos", ...defaultBucketProps
    });

    const transcribeTriggerRole = new iam.Role(this, "TranscribeTriggerRole", {
      roleName: "TranscribeTriggerRole",
      assumedBy: new iam.ServicePrincipal("lambda.amazonaws.com"),
      description: "Awesome role for triggering AWS transcribe",
      path: '/',
      inlinePolicies: {
        "TranscribeTriggerPolicy": new iam.PolicyDocument({
          statements: [new iam.PolicyStatement({
            actions: [
              "s3:GetObject",
              "s3:ListBucket",
            ],
            effect: iam.Effect.ALLOW,
            resources: [
              rowVideoS3bucket.bucketArn,
              rowVideoS3bucket.bucketArn + '/*',
            ],
          }), new iam.PolicyStatement({
            effect: iam.Effect.ALLOW,
            actions: [
              "s3:PutObject"
            ],
            resources: [
              transcribedVideoS3bucket.bucketArn,
              transcribedVideoS3bucket.bucketArn + '/*',
            ],
          }),
          new iam.PolicyStatement({
            actions: [
              "transcribe:StartTranscriptionJob"
            ],
            effect: iam.Effect.ALLOW,
            resources: ["*"],
          }), new iam.PolicyStatement({
            effect: iam.Effect.ALLOW,
            resources: ["*"],
            actions: [
              "logs:CreateLogGroup",
              "logs:CreateLogStream",
              "logs:PutLogEvents"
            ],
          })
          ]
        }),
      },
    });

    const transcribeTriggerFunction = new lambda.Function(this, "TranscribeTriggerFunction", {
      runtime: lambda.Runtime.NODEJS_16_X,
      handler: "index.lambdaHandler",
      role: transcribeTriggerRole,
      code: lambda.Code.fromInline(TranscribeTriggerFunctionCode),
      environment: {
        "TRANSCRIBED_VIDEOS3_BUCKET_NAME": transcribedVideoS3bucket.bucketName,
      }
    });

    transcribeTriggerFunction.addEventSource(new S3EventSource(rowVideoS3bucket, {
      events: [s3.EventType.OBJECT_CREATED],
      filters: [{ suffix: '.mp4' }], // optional
    }));

    const myAwesomeTopic = new sns.Topic(this, "MyAwesomeTopic", {
      displayName: "TranscribeTriggerTopic",
      topicName: "TranscribeTriggerTopic",
    });

    transcribedVideoS3bucket.addEventNotification(
      s3.EventType.OBJECT_CREATED,
      new s3Notifications.SnsDestination(myAwesomeTopic),
      { suffix: '.json' }
    );

    myAwesomeTopic.addSubscription(new snsSubscriptions.EmailSubscription(
      emailAddress.value.toString()
    )
    );


    const repository = new codecommit.Repository(this, 'Repository', {
      repositoryName: 'BatchServiceRepository',
      code: codecommit.Code.fromDirectory(path.join(__dirname, '../assets/batch/'), 'main'),
    });

    const registry = new ecr.Repository(this, 'RegistryWithBatchImages', {
      repositoryName: 'registry-with-batch-images',
      autoDeleteImages: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    const codeBuildRole = new iam.Role(this, "CodeBuildRole", {
      roleName: "CodeBuildRole",
      assumedBy: new iam.ServicePrincipal("codebuild.amazonaws.com"),
      description: "Build Role for CodeBuild",
      path: '/',
      inlinePolicies: {
        "CodeBuildPolicy": new iam.PolicyDocument({
          statements: [new iam.PolicyStatement({
            actions: [
              "codecommit:*",
            ],
            effect: iam.Effect.ALLOW,
            resources: [
              repository.repositoryArn,
            ],
          }), new iam.PolicyStatement({
            effect: iam.Effect.ALLOW,
            actions: [
              "ecr:GetAuthorizationToken",
              "ecr:BatchCheckLayerAvailability",
              "ecr:InitiateLayerUpload",
              "ecr:DescribeRepositories",
              "ecr:ListImages",
            ],
            resources: ["*"],
          }),
          new iam.PolicyStatement({
            actions: [
              "ecr:CompleteLayerUpload",
              "ecr:InitiateLayerUpload",
              "ecr:PutImage",
              "ecr:UploadLayerPart",
              "ecr:ListImages",
            ],
            effect: iam.Effect.ALLOW,
            resources: [
              registry.repositoryArn,
            ],
          }),
          ]
        }),
      },
    });

    const codebuildProject = new codebuild.Project(this, 'Project', {
      projectName: 'RegistryWithBatchImagesProject',
      source: codebuild.Source.codeCommit({ repository }),
      role: codeBuildRole,
      environment: {
        privileged: true,
      },
      buildSpec: codebuild.BuildSpec.fromObject({
        version: '0.2',
        phases: {
          pre_build: {
            commands: [
              'echo "Hello, CodeBuild!"',
              "aws ecr get-login-password --region " +
              cdk.Stack.of(this).region +
              " | docker login --username AWS --password-stdin " +
              cdk.Stack.of(this).account + ".dkr.ecr." +
              cdk.Stack.of(this).region + ".amazonaws.com",
            ],
          },
          build: {
            commands: [
              'echo Build started on`date`',
              'echo Building the Docker image...',
              'docker build -t batch:latest .',
              "docker tag batch:latest " + registry.repositoryUri + ":latest",
            ]
          },
          post_build: {
            commands: [
              'echo Build completed on`date`',
              'echo Pushing the Docker image...',
              "docker push " + registry.repositoryUri + ":latest"
            ]
          }
        },
      }),

    });

    const lambdaRunOnceRole = new iam.Role(this, "LambdaRunOnceRole", {
      roleName: "LambdaRunOnceRole",
      assumedBy: new iam.ServicePrincipal("lambda.amazonaws.com"),
      description: "Trigger Role for Lambda which invoke AWS CodeBuild After creation - only once",
      path: '/',
      inlinePolicies: {
        "LambdaRunOncePolicy": new iam.PolicyDocument({
          statements: [new iam.PolicyStatement({
            effect: iam.Effect.ALLOW,
            actions: [
              "codebuild:StartBuild"
            ],
            resources: ["*"],
          })
          ]
        }),
      },
    });


    const RunOnceTrigger = new triggers.TriggerFunction(this, 'CodeBuildOnlyOnceTrigger', {
      runtime: lambda.Runtime.NODEJS_16_X,
      handler: 'index.lambdaHandler',
      code: lambda.Code.fromInline(RunOnceFunctionCode),
      role: lambdaRunOnceRole,
      environment: {
        CODE_BUILD_PROJECT_NAME: codebuildProject.projectName,
      },
      executeAfter: [
        codebuildProject
      ]
    });

    const orderedComputeEnvironment: batch.OrderedComputeEnvironment = {
      computeEnvironment: new batch.FargateComputeEnvironment(this, 'spotEnv', {
        vpc: getExistingVpc,
        spot: true,
      }),
      order: 1,
    };

    const jobQueue = new batch.JobQueue(this, 'JobQueue', {
      jobQueueName: 'JobQueue',
      priority: 1,
      computeEnvironments: [
        orderedComputeEnvironment,
      ]
    });

    const inContainerBatchRole = new iam.Role(this, "InContainerBatchRole", {
      roleName: "InContainerBatchRole",
      assumedBy: new iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
      description: "Role for ECS Batch",
      path: '/',
      inlinePolicies: {
        "InContainerPolicy": new iam.PolicyDocument({
          statements: [new iam.PolicyStatement({
            actions: [
              "s3:GetObject",
              "s3:ListBucket",
            ],
            effect: iam.Effect.ALLOW,
            resources: [
              rowVideoS3bucket.bucketArn,
              rowVideoS3bucket.bucketArn + '/*',
              videoToLocalisationS3bucket.bucketArn,
              videoToLocalisationS3bucket.bucketArn + '/*',
            ],
          }), new iam.PolicyStatement({
            effect: iam.Effect.ALLOW,
            actions: [
              "s3:PutObject"
            ],
            resources: [
              videoOutputS3bucket.bucketArn,
              videoOutputS3bucket.bucketArn + '/*',
            ],
          }), new iam.PolicyStatement({
            effect: iam.Effect.ALLOW,
            actions: [
              "ecr:BatchGetImage",
              "ecr:GetDownloadUrlForLayer"
            ],
            resources: [
              registry.repositoryArn,
            ],
          }), new iam.PolicyStatement({
            effect: iam.Effect.ALLOW,
            actions: [
              "ecr:GetAuthorizationToken",
              "translate:*",
              "polly:*"
            ],
            resources: ["*"],
          }), new iam.PolicyStatement({
            effect: iam.Effect.ALLOW,
            resources: ["*"],
            actions: [
              "logs:CreateLogGroup",
              "logs:CreateLogStream",
              "logs:PutLogEvents"
            ],
          }),
          ]
        }),
      }
    });

    const jobDefinition = new batch.EcsJobDefinition(this, 'JobDefn', {
      jobDefinitionName: 'JobDefn',
      container: new batch.EcsFargateContainerDefinition(this, 'containerDefn', {
        image: ecs.ContainerImage.fromRegistry(registry.repositoryUri + ":latest"),
        cpu: 4.0,
        memory: cdk.Size.mebibytes(8192),
        assignPublicIp: true,
        environment: {
          "INVIDEO": "s3://initial-videos/video.mp4",
          "INSUBTITLES": "s3://transcribed-to-review/transcribe_cfadc0531765c2f6_video.mp4.json",
          "OUTBUCKET": "transcribed-to-review",
          "OUTLANG": "es de",
          "REGION": "eu-central-1"
        },
        jobRole: inContainerBatchRole,
        executionRole: inContainerBatchRole,
      }),
    });

    const lambdaTriggerBatchRole = new iam.Role(this, "LambdaTriggerBatchRole", {
      roleName: "LambdaTriggerBatchRole",
      assumedBy: new iam.ServicePrincipal("lambda.amazonaws.com"),
      description: "Trigger Role for Lambda which invoke AWS batch",
      path: '/',
      inlinePolicies: {
        "BatchTriggerPolicy": new iam.PolicyDocument({
          statements: [new iam.PolicyStatement({
            effect: iam.Effect.ALLOW,
            actions: [
              "batch:SubmitJob",
              "batch:DescribeJobs",
              "batch:TerminateJob"
            ],
            resources: ["*"],
          })
          ]
        }),
      },
    });

    const batchTriggerFunction = new lambda.Function(this, "BatchTriggerFunction", {
      runtime: lambda.Runtime.NODEJS_16_X,
      handler: "index.lambdaHandler",
      role: lambdaTriggerBatchRole,
      code: lambda.Code.fromInline(BatchTriggerFunctionCode),
      environment: {
        "JOB_DEFINITION_NAME": jobDefinition.jobDefinitionName,
        "JOB_QUEUE_NAME": jobQueue.jobQueueName,
        "OUTPUT_BUCKET_NAME": videoOutputS3bucket.bucketName,
        "VIDEO_BUCKET_NAME": rowVideoS3bucket.bucketName,
      }
    });

    videoToLocalisationS3bucket.addEventNotification(
      s3.EventType.OBJECT_CREATED,
      new s3Notifications.LambdaDestination(batchTriggerFunction),
      { suffix: '.json' }
    );

    videoOutputS3bucket.addEventNotification(
      s3.EventType.OBJECT_CREATED,
      new s3Notifications.SnsDestination(myAwesomeTopic),
      { suffix: '.mp4' }
    );
  }
}