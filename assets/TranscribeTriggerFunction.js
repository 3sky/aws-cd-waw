const AWS = require('aws-sdk');
const crypto = require('crypto');

const TranscribedVideoS3bucketName = process.env.TRANSCRIBED_VIDEOS3_BUCKET_NAME;

exports.lambdaHandler = async (event, context) => {
    const s3 = new AWS.S3();
    const transcribe = new AWS.TranscribeService();

    // Get the object key and bucket name from the S3 event notification
    const bucketName = event.Records[0].s3.bucket.name;
    const objectKey = event.Records[0].s3.object.key;

    // Start transcription job
    await transcribe.startTranscriptionJob({
        TranscriptionJobName: 'transcribe_' + crypto.randomBytes(8).toString("hex") + '_' + objectKey,
        Media: { MediaFileUri: `s3://${bucketName}/${objectKey}` },
        MediaFormat: 'mp4',
        LanguageCode: 'en-US',
        OutputBucketName: `${TranscribedVideoS3bucketName}`,
    }).promise();

    return {
        statusCode: 200,
        body: 'Transcription job started successfully.',
    };
};
