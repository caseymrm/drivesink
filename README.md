DriveSink
=========

> ## ⚠️ Deprecated — Amazon Drive shut down on December 31, 2023
>
> Amazon discontinued the Amazon Drive consumer service ([announcement](https://www.aboutamazon.com/news/devices/update-on-amazon-drive-as-we-continue-to-focus-on-amazon-photos)) at the end of 2023. The Cloud Drive API this tool depended on no longer exists, so **DriveSink can no longer upload or sync anything**. This repository is archived; issues and PRs are closed.
>
> ### Alternatives
> If you're looking for a command-line photo/file sync tool, consider:
> - **[rclone](https://rclone.org/)** — supports 70+ backends including S3, Backblaze B2, Google Drive, Dropbox, OneDrive, and dozens more
> - **[Amazon Photos](https://www.amazon.com/photos)** — still available to Prime members for photo/video storage (no general file storage, no public API)
> - **AWS S3 / Glacier Deep Archive** — for cheap long-term archival via the AWS CLI or rclone
> - **[Backblaze B2](https://www.backblaze.com/cloud-storage)** — inexpensive S3-compatible object storage
>
> Thanks to everyone who used, forked, and filed issues over the years.

---

A tool for syncing photos with Amazon Cloud Drive from the
command-line. Also a way of getting an access token to play with the
Cloud Drive API without registering an application. See
<a href="https://drivesink.appspot.com" target="_blank">https://drivesink.appspot.com</a> for more details.
