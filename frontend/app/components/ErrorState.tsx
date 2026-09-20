'use client';

export default function ErrorState({ title, message }: { title: string; message: string }) {
  return (
    <div role="alert" className="p-4 bg-red-950 border border-red-800 rounded-lg">
      <h3 className="font-semibold text-red-200">{title}</h3>
      <p className="text-sm text-red-300 mt-1">{message}</p>
    </div>
  );
}
