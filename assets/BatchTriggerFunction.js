const AWS = require('aws-sdk');

const OutputBucketName = process.env.OUTPUT_BUCKET_NAME;
const VideoBucketURL = process.env.VIDEO_BUCKET_NAME;
const JobDefinitionName = process.env.JOB_DEFINITION_NAME;
const JobQueueName = process.env.JOB_QUEUE_NAME

exports.lambdaHandler = async (event, context) => {

    // Get the object key and bucket name from the S3 event notification
    const subtitlesJSON = event.Records[0].s3.object.key;
    const subtitlesBucketName = event.Records[0].s3.bucket.name;

    const regex = /[^_]+_(.+)\.json$/;
    const match = subtitlesJSON.match(regex);

    const filenameWithExtension = match[1];
    const videoName = filenameWithExtension.substring(
        filenameWithExtension.indexOf('_') + 1
    );

    const videoURI = "s3://" + VideoBucketURL + "/" + videoName;
    const subtitlesURI = "s3://" + subtitlesBucketName + "/" + subtitlesJSON;

    console.log("videoName: ", videoURI);
    console.log("subtitlesURI: ", subtitlesURI);

    const batch = new AWS.Batch();

    const params = {
        jobName: "jobName",
        jobQueue: JobQueueName,
        jobDefinition: JobDefinitionName,
        containerOverrides: {
            environment: [
                {
                    name: 'INVIDEO',
                    value: videoURI,
                },
                {

                    name: "INSUBTITLES",
                    value: subtitlesURI,
                },
                {

                    name: "OUTBUCKET",
                    value: OutputBucketName,
                },
            ],
        },
    };

    try {
        const response = await batch.submitJob(params).promise();
        console.log('Job submitted successfully:', response);
        return response;
    } catch (error) {
        console.error('Error submitting job:', error);
        throw error;
    };

};
