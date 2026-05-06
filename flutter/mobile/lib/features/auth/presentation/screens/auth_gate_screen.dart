import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/config/supabase_config.dart';

class AuthGateScreen extends StatelessWidget {
  const AuthGateScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 520),
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    'Fulbito Stats',
                    style: Theme.of(context).textTheme.displaySmall,
                  ),
                  const SizedBox(height: 12),
                  Text(
                    'Base inicial del MVP. La siguiente pantalla real a implementar es login con Supabase Auth.',
                    style: Theme.of(context).textTheme.bodyLarge,
                  ),
                  const SizedBox(height: 24),
                  if (!SupabaseConfig.isConfigured)
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(20),
                        child: Text(
                          'Falta configurar SUPABASE_URL y SUPABASE_ANON_KEY. Mientras tanto, la navegación queda en modo stub.',
                          style: Theme.of(context).textTheme.bodyMedium,
                        ),
                      ),
                    ),
                  const SizedBox(height: 24),
                  FilledButton(
                    onPressed: () => context.go('/groups'),
                    child: const Text('Continuar al selector de grupos'),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
