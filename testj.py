import time

from mite.datapools import S3IterableDataPool


# dp = s_datapool(
#     bucket_name="id-s3-skyid-dev-nft-dashboard-eu-west-1",
#     prefix="kafkabackups/",
#     filenames_only=True,
# )

start_time = time.time()
dp = S3IterableDataPool(
    bucket_name="id-s3-skyid-dev-nft-dashboard-eu-west-1", prefix="kafkabackups/"
)
end_time = time.time()
elapsed_time = end_time - start_time
print(f"{elapsed_time:.4f} seconds to complete.")


async def journey(ctx, filename, file_contents):
    print("running journey", filename)


# s3_client = boto3.client("s3")
# bucket_name = "id-s3-skyid-dev-nft-dashboard-eu-west-1"
# for i in range(840):
#     s3_client.upload_file(
#         "PROFILE_CREATED.json", bucket_name, f"kafkabackups/PROFILE_CREATED2_{i}.json"
#     )
