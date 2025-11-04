import { NextRequest, NextResponse } from 'next/server';
import nodemailer from 'nodemailer';
import { auth } from '@/auth';

export async function POST(req: NextRequest) {
  try {
    // Get feedback data from request body
    const { feedback, email, rating } = await req.json();

    if (!feedback || feedback.trim() === '') {
      return NextResponse.json(
        { error: 'Feedback content is required' },
        { status: 400 }
      );
    }

    // Get session (if user is logged in)
    const session = await auth();
    const userEmail = session?.user?.email || email || 'Anonymous User';
    const userName = session?.user?.name || 'Anonymous User';

    // Create transporter with SMTP configuration
    const transporter = nodemailer.createTransport({
      host: process.env.SMTP_HOST,
      port: Number(process.env.SMTP_PORT) || 465,
      secure: true,
      auth: {
        user: process.env.SMTP_USER,
        pass: process.env.SMTP_PASSWORD,
      },
    });

    // Prepare email content
    const emailSubject = `Rhesis AI Feedback - ${rating ? `Rating: ${rating}/5` : 'New Feedback'}`;
    const emailText = `
User Feedback:
--------------
From: ${userName} (${userEmail})
${rating ? `Rating: ${rating}/5 stars` : ''}

Feedback:
${feedback}
    `;

    const emailHtml = `
<h2>User Feedback</h2>
<p><strong>From:</strong> ${userName} (${userEmail})</p>
${rating ? `<p><strong>Rating:</strong> ${rating}/5 stars</p>` : ''}

<h3>Feedback:</h3>
<p>${feedback.replace(/\n/g, '<br/>')}</p>
    `;

    // Send email
    const mailOptions = {
      from: 'engineering@rhesis.ai',
      to: 'hello@rhesis.ai',
      replyTo: email || 'noreply@rhesis.ai',
      subject: emailSubject,
      text: emailText,
      html: emailHtml,
    };

    await transporter.sendMail(mailOptions);

    return NextResponse.json({
      success: true,
      message: 'Feedback sent successfully',
    });
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to send feedback' },
      { status: 500 }
    );
  }
}
